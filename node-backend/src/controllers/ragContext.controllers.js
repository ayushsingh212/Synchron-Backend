import ragContext from "../models/ragContext.model.js";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import { GetObjectCommand } from "@aws-sdk/client-s3";
import asyncHandler from "../utils/asyncHandler.js";
import { s3, generateSignedUrl } from "../utils/awsS3.js";
import { s3Client } from "../utils/ragEngine.js";

import extract from "pdf-text-extract";
import fs from "fs";

async function downloadPdfFromS3(key) {
  const command = new GetObjectCommand({
    Bucket: process.env.AWS_S3_BUCKET_NAME,
    Key: key,
  });

  const response = await s3Client.send(command);

  const chunks = [];
  for await (const chunk of response.Body) {
    chunks.push(chunk);
  }

  return Buffer.concat(chunks);
}

async function extractPdfText(buffer) {
  const tempFile = "temp.pdf";
  fs.writeFileSync(tempFile, buffer);

  return new Promise((resolve, reject) => {
    extract(tempFile, (err, pages) => {
      fs.unlinkSync(tempFile);

      if (err) return reject(err);
      resolve(pages.join("\n"));
    });
  });
}



// async function extractPdfText(pdfBuffer) {
//   return new Promise((resolve, reject) => {
//     const pdfParser = new PDFParser();
    
//     pdfParser.on("pdfParser_dataError", (errData) => {
//       console.error("PDF parsing error:", errData.parserError);
//       reject(new ApiError(500, "Failed to extract text from PDF"));
//     });
    
//     pdfParser.on("pdfParser_dataReady", (pdfData) => {
//       try {
//         // Extract text from all pages
//         let fullText = "";
//         if (pdfData.Pages) {
//           pdfData.Pages.forEach((page) => {
//             if (page.Texts) {
//               page.Texts.forEach((text) => {
//                 if (text.R) {
//                   text.R.forEach((r) => {
//                     if (r.T) {
//                       fullText += decodeURIComponent(r.T) + " ";
//                     }
//                   });
//                 }
//               });
//               fullText += "\n";
//             }
//           });
//         }
//         resolve(fullText.trim());
//       } catch (error) {
//         reject(new ApiError(500, "Failed to process PDF content"));
//       }
//     });
    
//     pdfParser.parseBuffer(pdfBuffer);
//   });
// }

//  async function extractPdfText(buffer) {
//   const pdf = openDocument(buffer);
//   let text = "";

//   for (let i = 0; i < pdf.pageCount; i++) {
//     text += extractPageText(pdf, i) + "\n";
//   }

//   return text;
// }


export const getAllFolders = asyncHandler(async (req, res) => {
  const organisationId = req.organisation._id;

  const contexts = await ragContext.find({ organisationId }).select('folderName createdAt updatedAt uploadedDocuments');

  return res.json(new ApiResponse(200, contexts, "Folders fetched successfully"));
});

export const deleteFolder = asyncHandler(async (req, res) => {
  const organisationId = req.organisation._id;
  const { folderName } = req.body;
  
  const context = await ragContext.findOneAndDelete({ organisationId, folderName });

  if (!context) throw new ApiError(404, "Context not found");
  return res.json(new ApiResponse(200, "Folder deleted successfully"));
});

export const createFolder = asyncHandler(async (req, res) => {
  const { folderName } = req.body;
  const organisationId = req.organisation._id;
  
  let context = await ragContext.findOne({ organisationId, folderName });
  if (context) throw new ApiError(400, "Folder with this name already exists");

  context = await ragContext.create({ organisationId, folderName, uploadedDocuments: [] });
  return res.json(new ApiResponse(201, context, "Folder created successfully"));
});


export const generateMultiplePresignedUploadUrls = async (files, folder = "synchron") => {
  try {
    const results = [];

    for (const file of files) {
      const fileName = file.fileName;
      const fileType = file.fileType;

      let ext = "";
      if (fileName.includes(".")) ext = fileName.split(".").pop();
      else if (fileType.includes("/")) ext = fileType.split("/").pop();

      const key = `${folder}/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

      const params = {
        Bucket: process.env.AWS_S3_BUCKET_NAME,
        Key: key,
        ContentType: fileType,
        Expires: 60
      };

      const uploadUrl = s3.getSignedUrl("putObject", params);

      results.push({
        uploadUrl,
        key,
        viewUrl: generateSignedUrl(key)
      });
    }

    return results;
  } catch (error) {
    console.error("Error generating multiple presigned URLs:", error);
    throw new ApiError(500, "Failed to generate multiple upload URLs");
  }
};

export const saveUploadedDocuments = asyncHandler(async (req, res) => {
  console.log("here is the req", req.organisation);
  const organisationId = req.organisation._id;
  console.log("Req.body", req.body);
  
  if (!organisationId) throw new ApiError(401, "Login first");
  const { folderName, documents } = req.body;

  let ctx = await ragContext.findOne({ organisationId, folderName });
  if (!ctx) ctx = await ragContext.create({ organisationId, folderName, uploadedDocuments: [] });

  documents.forEach((doc) => {
    ctx.uploadedDocuments.push({
      fileName: doc.fileName,
      key: doc.key,
      viewUrl: doc.viewUrl
    });
  });

  await ctx.save();

  return res.json(new ApiResponse(200, ctx));
});

export const extractTextForDocument = asyncHandler(async (req, res) => {
  const organisationId = req.organisation._id;
  const { folderName, key } = req.body;

  const ctx = await ragContext.findOne({ organisationId, folderName });
  if (!ctx) throw new ApiError(404, "Context not found");

  const doc = ctx.uploadedDocuments.find((d) => d.key === key);
  if (!doc) throw new ApiError(404, "Document not found");

  const pdfBuffer = await downloadPdfFromS3(key);
  const text = await extractPdfText(pdfBuffer);

  doc.extractedText = text;
  await ctx.save();

  return res.json(new ApiResponse(200, doc));
});


export const extractAllDocumentsText = asyncHandler(async (req, res) => {
  const organisationId = req.organisation._id;
  const { folderName } = req.body;

  const ctx = await ragContext.findOne({ organisationId, folderName });

  console.log("Here is the context ", ctx);
  if (!ctx) throw new ApiError(404, "Context not found");

  for (let doc of ctx.uploadedDocuments) {
    if (!doc.key) continue;
    
    try {
      const pdfBuffer = await downloadPdfFromS3(doc.key);
      const text = await extractPdfText(pdfBuffer);
      doc.extractedText = text;
    } catch (error) {
      console.error(`Error extracting text for ${doc.fileName}:`, error);
      doc.extractedText = "Error: Failed to extract text";
    }
  }

  await ctx.save();

  return res.json(new ApiResponse(200, ctx.uploadedDocuments));
});


export const getAllDocuments = asyncHandler(async (req, res) => {
  const organisationId = req.organisation._id;
  const { folderName } = req.query;

  const ctx = await ragContext.findOne({ organisationId, folderName });
  if (!ctx) throw new ApiError(404, "Context not found");

  return res.json(new ApiResponse(200, ctx.uploadedDocuments));
});

export const deleteDocument = asyncHandler(async (req, res) => {
  const organisationId = req.organisation._id;
  const { folderName, key } = req.body;

  const ctx = await ragContext.findOne({ organisationId, folderName });
  if (!ctx) throw new ApiError(404, "Context not found");

  ctx.uploadedDocuments = ctx.uploadedDocuments.filter((d) => d.key !== key);

  await ctx.save();

  return res.json(new ApiResponse(200, "Document deleted"));
});

export const deleteEntireContext = asyncHandler(async (req, res) => {
  const organisationId = req.organisation._id;
  const { folderName } = req.body;

  const ctx = await ragContext.findOneAndDelete({ organisationId, folderName });
  if (!ctx) throw new ApiError(404, "Context not found");

  return res.json(new ApiResponse(200, "Context deleted"));
});