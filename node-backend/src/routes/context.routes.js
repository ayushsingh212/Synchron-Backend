


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
import { verifySenateToken } from "../middlewares/senate.middleware.js";

const router = express.Router();


router.use(verifyJWT)
router.use(verifySenateToken)


router.post("/upload-urls", async (req, res) => {
  const { files } = req.body;

  const urls = await generateMultiplePresignedUploadUrls(files); // folder auto = synchron

  res.json({ success: true, data: urls });
});

router.get("/folders",  getAllFolders);
router.post("/createFolder",  createFolder);
router.delete("/deleteFolder",  deleteFolder);
router.post("/save-docs",  saveUploadedDocuments);

router.post("/extract-one",  extractTextForDocument);

router.post("/extract-all",  extractAllDocumentsText);

router.get("/docs",  getAllDocuments);

router.post("/delete-doc",  deleteDocument);

router.post("/delete-context",  deleteEntireContext);

export default router;
