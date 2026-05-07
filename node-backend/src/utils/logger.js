import { createLogger, format, transports } from "winston";

const { combine, timestamp, printf, colorize, errors } = format;

const logFormat = printf(({ level, message, timestamp, stack, ...meta }) => {
  const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : "";
  return `${timestamp} [${level}]: ${stack || message}${metaStr}`;
});

const logger = createLogger({
  level: process.env.NODE_ENV === "production" ? "info" : "debug",
  format: combine(
    errors({ stack: true }),
    timestamp({ format: "YYYY-MM-DD HH:mm:ss" }),
    logFormat
  ),
  defaultMeta: { service: "synchron-api" },
  transports: [
    // Console output (colorized in development)
    new transports.Console({
      format: combine(
        colorize(),
        timestamp({ format: "HH:mm:ss" }),
        logFormat
      ),
    }),

    // File: all logs
    new transports.File({
      filename: "logs/combined.log",
      maxsize: 5 * 1024 * 1024, // 5MB
      maxFiles: 5,
    }),

    // File: errors only
    new transports.File({
      filename: "logs/error.log",
      level: "error",
      maxsize: 5 * 1024 * 1024,
      maxFiles: 5,
    }),
  ],

  // Don't crash on unhandled exceptions
  exitOnError: false,
});

export default logger;
