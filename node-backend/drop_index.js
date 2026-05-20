import mongoose from "mongoose";
import dns from "node:dns";
import dotenv from "dotenv";
import { dirname } from "path";
import { fileURLToPath } from "url";

// Force Node.js to use Google Public DNS for SRV lookups (needed for local ISPs that block SRV records)
dns.setServers(["8.8.8.8", "8.8.4.4"]);

const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: __dirname + "/.env" });

const MONGODB_URL = process.env.MONGODB_URL;
// Mongoose by default connects to the 'test' database if no database is specified in the URL path.
const DB_NAME = "test";

console.log("Connecting to MongoDB database:", DB_NAME);

mongoose.connect(MONGODB_URL, { dbName: DB_NAME })
  .then(async () => {
    console.log("Connected successfully to database:", DB_NAME);
    const db = mongoose.connection.db;
    
    // List indexes
    const indexes = await db.collection("organisations").indexes();
    console.log("Current indexes on 'organisations':", indexes.map(i => i.name));
    
    // Check if the unique index exists
    const hasIndex = indexes.some(i => i.name === "senates.seneteEmail_1");
    
    if (hasIndex) {
      console.log("Dropping unique index 'senates.seneteEmail_1'...");
      await db.collection("organisations").dropIndex("senates.seneteEmail_1");
      console.log("Index dropped successfully!");
    } else {
      console.log("Unique index 'senates.seneteEmail_1' was not found.");
    }
    
    process.exit(0);
  })
  .catch(err => {
    console.error("Error occurred:", err);
    process.exit(1);
  });
