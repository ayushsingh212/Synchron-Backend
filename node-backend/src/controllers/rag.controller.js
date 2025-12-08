// import fs from "fs";
// import path from "path";
// import { createRagIndexFromPDFs, loadIndexAndQuery } from "../utils/ragEngine.js";
// import { generatePresignedUploadUrl } from "../utils/awsS3.js";

// const INDEX_DIR = "./rag_indexes";
// if (!fs.existsSync(INDEX_DIR)) fs.mkdirSync(INDEX_DIR);

// export const createUserRag = async (req, res) => {
//   const {  pdfKeys } = req.body;
//   const userId = req.user?._id;
//    console.log("Trying to fetch from S3:", pdfKeys);

//   const indexData = await createRagIndexFromPDFs(userId, pdfKeys);

//   fs.writeFileSync(
//     path.join(INDEX_DIR, `${userId}.json`),
//     JSON.stringify(indexData)
//   );

//   res.json({ message: "RAG index created successfully" });
// };

// export const askRag = async (req, res) => {
//   const { userId, query } = req.body;

//   const filePath = path.join(INDEX_DIR, `${userId}.json`);
//   if (!fs.existsSync(filePath)) {
//     return res.status(400).json({ error: "No RAG data for this user" });
//   }

//   const json = JSON.parse(fs.readFileSync(filePath, "utf8"));
//   const index = await loadIndex(json);

//   const result = await index.asQueryEngine().query(query);

//   res.json({ answer: result.toString() });
// };

// export const resetUserRag = async (req, res) => {
//   const { userId } = req.body;

//   const filePath = path.join(INDEX_DIR, `${userId}.json`);
//   if (fs.existsSync(filePath)) fs.unlinkSync(filePath);

//   res.json({ message: "RAG reset for user" });
// };
export const getPresignedUploadUrl = async (req, res) => {
  try {
    const { fileName, fileType } = req.body;

    if (!fileName || !fileType) {
      return res.status(400).json({ message: "fileName and fileType required" });
    }

    const allowedTypes = [
      "application/pdf",
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/svg+xml",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/plain",
    ];

    if (!allowedTypes.includes(fileType)) {
      return res.status(400).json({ message: "Unsupported file type" });
    }

    const result = await generatePresignedUploadUrl(fileName, fileType);

    return res.status(200).json({
      uploadUrl: result.uploadUrl,
      key: result.key,
      viewUrl: result.viewUrl,
    });
  } catch (err) {
    console.error("Presign error:", err);
    res.status(500).json({ message: "Failed to generate upload URL" });
  }
};
// import fs from "fs";
// import path from "path";
// import { createRagIndexFromPDFs, loadIndexAndQuery } from "../utils/ragEngine.js";


// Create directory if it doesn't exist
// if (!fs.existsSync(INDEX_DIR)) {
//   fs.mkdirSync(INDEX_DIR, { recursive: true });
// }

// Create RAG index from PDFs
// export const createUserRag = async (req, res) => {
//   try {
//     const { pdfKeys } = req.body;
//     const userId = req.user?._id;
    
//     console.log("Creating RAG index for user:", userId);
//     console.log("PDF keys:", pdfKeys);

//     const indexData = await createRagIndexFromPDFs(userId, pdfKeys);

//     // fs.writeFileSync(
//     //   path.join(INDEX_DIR, `${userId}.json`),
//     //   JSON.stringify(indexData)
//     // );

//     res.json({ 
//       success: true,
//       message: "RAG index created successfully" 
//     });
//   } catch (error) {
//     console.error("Error creating RAG:", error);
//     res.status(500).json({ 
//       success: false,
//       message: "Failed to create RAG index",
//       error: error.message 
//     });
//   }
// };


// export const queryUserRag = async (req, res) => {
//   try {
//     const { query } = req.body;
//     const userId = req.user?._id;

//     const indexPath = path.join(INDEX_DIR, `${userId}.json`);
    
//     if (!fs.existsSync(indexPath)) {
//       return res.status(404).json({ 
//         success: false,
//         message: "RAG index not found. Please upload PDFs first." 
//       });
//     }

//     const indexData = JSON.parse(fs.readFileSync(indexPath, "utf-8"));
//     const answer = await loadIndexAndQuery(indexData, query);

//     res.json({ 
//       success: true,
//       query,
//       answer 
//     });
//   } catch (error) {
//     console.error("Error querying RAG:", error);
//     res.status(500).json({ 
//       success: false,
//       message: "Failed to query RAG system",
//       error: error.message 
//     });
//   }
// };

// // Delete user's RAG index
// export const deleteUserRag = async (req, res) => {
//   try {
//     const userId = req.user?._id;
//     const indexPath = path.join(INDEX_DIR, `${userId}.json`);

//     if (fs.existsSync(indexPath)) {
//       fs.unlinkSync(indexPath);
//     }

//     res.json({ 
//       success: true,
//       message: "RAG index deleted successfully" 
//     });
//   } catch (error) {
//     console.error("Error deleting RAG:", error);
//     res.status(500).json({ 
//       success: false,
//       message: "Failed to delete RAG index",
//       error: error.message 
//     });
//   }
// };
