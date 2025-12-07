


import express from "express";
import { verifyJWT } from "../middlewares/auth.middleware.js";

import {
  generateMultiplePresignedUploadUrls,
  saveUploadedDocuments,
  extractTextForDocument,
  extractAllDocumentsText,
  getAllDocuments,
  deleteDocument,
  deleteEntireContext,
  getAllFolders,
  createFolder,
  deleteFolder
} from "../controllers/ragContext.controllers.js";

const router = express.Router();

router.post("/upload-urls", verifyJWT, async (req, res) => {
  const { files } = req.body;

  const urls = await generateMultiplePresignedUploadUrls(files); // folder auto = synchron

  res.json({ success: true, data: urls });
});

router.get("/folders", verifyJWT, getAllFolders);
router.post("/createFolder", verifyJWT, createFolder);
router.delete("/deleteFolder", verifyJWT, deleteFolder);
router.post("/save-docs", verifyJWT, saveUploadedDocuments);

router.post("/extract-one", verifyJWT, extractTextForDocument);

router.post("/extract-all", verifyJWT, extractAllDocumentsText);

router.get("/docs", verifyJWT, getAllDocuments);

router.post("/delete-doc", verifyJWT, deleteDocument);

router.post("/delete-context", verifyJWT, deleteEntireContext);

export default router;
