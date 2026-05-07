import mongoose from "mongoose";
import dns from "node:dns";
import logger from "../utils/logger.js";

// Force Node.js to use Google Public DNS for SRV lookups
dns.setServers(["8.8.8.8", "8.8.4.4"]);

const connectDB = async function () {
  const mongoUrl = process.env.MONGODB_URL;

  if (!mongoUrl) {
    logger.error("MONGODB_URL is not defined in environment variables");
    process.exit(1);
  }

  try {
    const connect = await mongoose.connect(mongoUrl);
    logger.info(`MongoDB connected: ${connect.connection.host}`);
  } catch (error) {
    logger.error("MongoDB connection error", { error: error.message });
    process.exit(1);
  }
};

export { connectDB };
