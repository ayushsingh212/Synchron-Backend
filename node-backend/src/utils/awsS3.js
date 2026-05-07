import AWS from "aws-sdk";
import fs from "fs";
import path from "path";
import ApiError from "./apiError.js";

const { AWS_S3_ID, AWS_SECRET, AWS_REGION } = process.env;

// Only configure AWS if credentials are present
if (AWS_S3_ID && AWS_SECRET) {
  AWS.config.update({
    accessKeyId: AWS_S3_ID,
    secretAccessKey: AWS_SECRET,
    region: AWS_REGION,
  });
}

export const s3 = new AWS.S3();

// Lazy-initialize CloudFront signer to avoid crashing on import
let cloudfrontSigner = null;

function getCloudFrontSigner() {
  if (cloudfrontSigner) return cloudfrontSigner;

  const keyPath = process.env.CLOUDFRONT_PRIVATE_KEY_PATH;
  const keyPairId = process.env.CLOUDFRONT_KEY_PAIR_ID;

  if (!keyPath || !keyPairId) {
    console.warn("CloudFront signing not configured — CLOUDFRONT_PRIVATE_KEY_PATH or CLOUDFRONT_KEY_PAIR_ID missing.");
    return null;
  }

  try {
    const privateKey = fs.readFileSync(keyPath, "utf8");
    cloudfrontSigner = new AWS.CloudFront.Signer(keyPairId, privateKey);
    return cloudfrontSigner;
  } catch (error) {
    console.error("Unable to read CloudFront private key:", error.message);
    return null;
  }
}

export const generateSignedUrl = (key) => {
  const signer = getCloudFrontSigner();
  if (!signer) {
    // Fallback to direct S3 URL if CloudFront is not configured
    return `https://${process.env.AWS_S3_BUCKET_NAME}.s3.amazonaws.com/${key}`;
  }

  const url = `${process.env.CLOUDFRONT_URL}/${key}`;
  return signer.getSignedUrl({
    url,
    expires: Math.floor(Date.now() / 1000) + 24 * 60 * 60,
  });
};

export const uploadToS3 = async (localFilePath, folder = "uploads") => {
  if (!localFilePath) return null;

  const safeUnlink = (filePath) => {
    try {
      if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    } catch (err) {
      console.warn("Failed to delete temp file:", err);
    }
  };

  try {
    const fileContent = await fs.promises.readFile(localFilePath);
    const fileName = path.basename(localFilePath);

    // Fixed: derive extension from fileName only (fileType was undefined before)
    let ext = "";
    if (fileName.includes(".")) {
      ext = fileName.split(".").pop();
    }

    const key = `${folder}/${Date.now()}.${ext}`;

    // Use path.extname for MIME type detection instead of removed mime-types import
    const mimeMap = {
      ".pdf": "application/pdf",
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".gif": "image/gif",
      ".webp": "image/webp",
      ".svg": "image/svg+xml",
      ".doc": "application/msword",
      ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      ".csv": "text/csv",
    };
    const fileExt = path.extname(fileName).toLowerCase();
    const mimeType = mimeMap[fileExt] || "application/octet-stream";

    if (!process.env.AWS_S3_BUCKET_NAME) {
      throw new Error("AWS_S3_BUCKET_NAME not defined in environment");
    }

    const uploadParams = {
      Bucket: process.env.AWS_S3_BUCKET_NAME,
      Key: key,
      Body: fileContent,
      ContentType: mimeType,
      ContentDisposition: "inline",
    };

    const result = await s3.upload(uploadParams).promise();

    safeUnlink(localFilePath);

    return {
      key,
      signedUrl: generateSignedUrl(key),
      s3Location: result.Location,
    };
  } catch (err) {
    safeUnlink(localFilePath);
    console.error("S3 upload failed:", err);
    return null;
  }
};

export const deleteFromS3 = async (key) => {
  if (!key) return;

  try {
    await s3
      .deleteObject({
        Bucket: process.env.AWS_S3_BUCKET_NAME,
        Key: key,
      })
      .promise();
    console.log("Deleted from S3:", key);
  } catch (err) {
    console.error("Failed to delete from S3:", err);
  }
};

export const generatePresignedUploadUrl = async (
  fileName,
  fileType,
  folder = "synchron"
) => {
  try {
    let ext = "";

    if (fileName.includes(".")) {
      ext = fileName.split(".").pop();
    } else if (fileType && fileType.includes("/")) {
      ext = fileType.split("/").pop();
    }

    const key = `${folder}/${Date.now()}.${ext}`;

    if (!process.env.AWS_S3_BUCKET_NAME) {
      throw new Error("AWS_S3_BUCKET_NAME not defined in environment");
    }

    const params = {
      Bucket: process.env.AWS_S3_BUCKET_NAME,
      Key: key,
      ContentType: fileType,
      Expires: 60,
    };

    const uploadUrl = s3.getSignedUrl("putObject", params);

    return {
      uploadUrl,
      key,
      viewUrl: generateSignedUrl(key),
    };
  } catch (error) {
    console.error("Error generating presigned URL:", error);
    throw new ApiError(500, "Failed to generate upload URL");
  }
};
