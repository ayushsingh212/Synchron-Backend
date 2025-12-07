import AWS from "aws-sdk";
import fs from "fs";
import path from "path";
import dotenv from "dotenv";
import  ApiError  from "./apiError.js";
import mime from "mime-types";
dotenv.config();
console.log("AWS_S3_ID:", process.env.AWS_S3_ID);
console.log("AWS_SECRET:", process.env.AWS_SECRET);
   
const AWS_S3_ID="AKIAY27STOW7JVJUF4ES"
const AWS_SECRET="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"
const AWS_REGION="ap-south-1"
AWS.config.update({
  accessKeyId: AWS_S3_ID,
  secretAccessKey: AWS_SECRET,
  region:AWS_REGION,
});

export const s3 = new AWS.S3();
if (!process.env.CLOUDFRONT_PRIVATE_KEY_PATH) {
  throw new ApiError(500, "Server busy ");
}
let pri = "sdhjd";
try {
  pri = fs.readFileSync(process.env.CLOUDFRONT_PRIVATE_KEY_PATH, "utf8") || " ";
} catch (error) {
  console.log("Unable to read the cdn", error);
}
const cloudfrontSigner = new AWS.CloudFront.Signer(
  process.env.CLOUDFRONT_KEY_PAIR_ID,
  pri
);
export const generateSignedUrl = (key) => {
  const url = `${process.env.CLOUDFRONT_URL}/${key}`;

  return cloudfrontSigner.getSignedUrl({
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
let ext = "";

if (fileName.includes(".")) {
  ext = fileName.split(".").pop();
} else if (fileType.includes("/")) {
  ext = fileType.split("/").pop();
}

const key = `${folder}/${Date.now()}.${ext}`;

    const mimeType = mime.lookup(fileName) || "application/octet-stream";
    console.log("here is you bucket name:", process.env.AWS_S3_BUCKET_NAME);
    if (!process.env.AWS_S3_BUCKET_NAME) {
      throw new Error("Bucket name not defined");
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
  fileName ,
  fileType,
  folder = "synchron"
) => {
  try {
let ext = "";

if (fileName.includes(".")) {
  ext = fileName.split(".").pop();
} else if (fileType.includes("/")) {
  ext = fileType.split("/").pop();
}

const key = `${folder}/${Date.now()}.${ext}`;

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
