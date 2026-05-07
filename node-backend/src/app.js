import express from "express";
import cors from "cors";
import cookieParser from "cookie-parser";
import rateLimit from "express-rate-limit";
import allRouter from "./routes/index.js";
import { noEmojiMiddleware } from "./middlewares/noEmoji.middleware.js";
import ApiError from "./utils/apiError.js";
import { ZodError } from "zod";
import logger from "./utils/logger.js";

const app = express();

const {FRONTEND_URL,FRONTEND_URL2,BACKEND_URL} = process.env;

const corsOptions = {
  origin: [FRONTEND_URL, FRONTEND_URL2, "http://localhost:5173"],
  methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  allowedHeaders: ["Content-Type", "Authorization"],
  credentials: true,
};
app.options("*", cors(corsOptions));

app.use(cors(corsOptions));

// Rate limiting
const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 200,
  message: { success: false, message: "Too many requests, please try again later" },
  standardHeaders: true,
  legacyHeaders: false,
});

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 15, // 15 login attempts per 15 minutes
  message: { success: false, message: "Too many login attempts, please try again after 15 minutes" },
  standardHeaders: true,
  legacyHeaders: false,
});

app.use(globalLimiter);

app.use(express.json({ limit: "100mb" }));
app.use(express.urlencoded({ extended: true, limit: "100mb" }));


app.use(express.static("public"));


app.use(cookieParser());

// Health check endpoint
app.get("/health", (req, res) => {
  res.status(200).json({
    status: "ok",
    service: "node-backend",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  });
});

app.use(noEmojiMiddleware);

// Apply stricter rate limiting to auth routes
app.use("/api/v1/organisation/login", authLimiter);
app.use("/api/v1/organisation/register", authLimiter);
app.use("/api/v1/senate/login", authLimiter);
app.use("/api/v1/verification/getOtp", authLimiter);

app.use("/api/v1", allRouter);



app.use((err, req, res, next) => {
  logger.error("Request error", { path: req.path, method: req.method, message: err.message, stack: err.stack });

  let statusCode = err.statusCode || 500;
  let message = err.message || "Internal Server Error";


  if (err instanceof ZodError) {
    statusCode = 400;

    return res.status(statusCode).json({
      success: false,
      message: "Validation failed",
      errors: err.errors.map(e => ({
        path: e.path.join("."),
        message: e.message
      })),
      data: null,
    });
  }


  if (err.name === "ValidationError") {
    statusCode = 400;

    return res.status(statusCode).json({
      success: false,
      message: "Validation error",
      errors: Object.values(err.errors).map(e => e.message),
      data: null,
    });
  }


  if (err.name === "CastError") {
    statusCode = 400;

    return res.status(statusCode).json({
      success: false,
      message: `Invalid ${err.path}: ${err.value}`,
      errors: [],
      data: null,
    });
  }

  if (err instanceof ApiError) {
    return res.status(statusCode).json({
      success: false,
      message: err.message,
      errors: err.errors || [],
      data: err.data || null,
    });
  }


  return res.status(statusCode).json({
    success: false,
    message,
    errors: [],
    data: null,
    stack: process.env.NODE_ENV === "development" ? err.stack : undefined,
  });
});




export default app;
