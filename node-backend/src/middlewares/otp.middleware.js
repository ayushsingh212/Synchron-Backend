import { createClient } from "redis";
import logger from "../utils/logger.js";

let redisClient = null;
let isConnected = false;

async function getRedisClient() {
  if (redisClient && isConnected) return redisClient;

  redisClient = createClient({
    url: process.env.REDIS_URL,
    socket: {
      reconnectStrategy: (retries) => {
        if (retries > 10) {
          logger.error("Redis: Max reconnection attempts reached");
          return new Error("Max reconnection attempts reached");
        }
        return Math.min(retries * 200, 3000);
      },
    },
  });

  redisClient.on("error", (err) => logger.error("Redis Client Error", { error: err.message }));
  redisClient.on("connect", () => {
    isConnected = true;
    logger.info("Redis connected successfully");
  });
  redisClient.on("disconnect", () => {
    isConnected = false;
  });

  try {
    // await redisClient.connect();
  } catch (err) {
    logger.error("Redis connection failed", { error: err.message });
    isConnected = false;
  }

  return redisClient;
}

// Initialize connection on first import (non-blocking)
getRedisClient().catch((err) =>
  logger.error("Redis initial connection failed", { error: err.message })
);

export { redisClient, getRedisClient };
