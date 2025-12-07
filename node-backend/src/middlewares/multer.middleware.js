// import multer from "multer";
// import path from "path";

// const storage = multer.diskStorage({
//   destination: function (req, file, cb) {
//     cb(null, "./public/temp");
//   },
//   filename: function (req, file, cb) {
//     const ext = path.extname(file.originalname);
//     const name = `${Date.now()}-${file.fieldname}${ext}`;
//     cb(null, name);
//   },
// });

// const fileFilter = (req, file, cb) => {
//   if (
//     file.mimetype.startsWith("image/") || 
//     file.mimetype === "application/pdf"
//   ) {
//     cb(null, true);
//   } else {
//     cb(new Error("Only image and PDF files are allowed"), false);
//   }
// };

// export const upload = multer({ storage, fileFilter });
import multer from "multer";

const storage = multer.memoryStorage(); // store file in memory, NOT disk

export const upload = multer({
  storage,
  limits: {
    fileSize: 10 * 1024 * 1024, // 10 MB per file
  }
});
