
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

// Resolve .env path relative to THIS file, not CWD
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.resolve(__dirname, "../.env") });

import app from "./app.js";
import { connectDB } from "./dB/db.connect.js";
import logger from "./utils/logger.js";

const PORT = process.env.PORT || 1000;

connectDB()
  .then(() => {
    app.listen(PORT, () => {
      logger.info(`Server running on http://localhost:${PORT}`);
    });
  })
  .catch((err) => {
    logger.error("Failed to connect to DB", { error: err.message });
    process.exit(1);
  });
