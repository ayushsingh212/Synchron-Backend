// import { VectorStoreIndex, Document, Settings } from "llamaindex";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
// import dotenv from "dotenv";
// import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf.mjs";
// import { Ollama } from "ollama";

// dotenv.config();

// const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || "http://localhost:11434";

// // Custom Ollama Embedding class with proper interface
// class OllamaEmbedding {
//   constructor(options = {}) {
//     this.model = options.model || "nomic-embed-text";
//     this.baseUrl = options.baseUrl || "http://localhost:11434";
//     this.ollama = new Ollama({ host: this.baseUrl });
//   }

//   async getTextEmbedding(text) {
//     const response = await this.ollama.embeddings({
//       model: this.model,
//       prompt: text,
//     });
//     return response.embedding;
//   }

//   async getQueryEmbedding(query) {
//     return this.getTextEmbedding(query);
//   }

//   // Required method for LlamaIndex
//   async getTextEmbeddingsBatch(texts) {
//     const embeddings = await Promise.all(
//       texts.map(text => this.getTextEmbedding(text))
//     );
//     return embeddings;
//   }
// }

// // Custom Ollama LLM class
// class OllamaLLM {
//   constructor(options = {}) {
//     this.model = options.model || "llama3.2";
//     this.baseUrl = options.config?.host || "http://localhost:11434";
//     this.ollama = new Ollama({ host: this.baseUrl });
//   }

//   async complete(params) {
//     const prompt = typeof params === 'string' ? params : params.prompt;
//     const response = await this.ollama.generate({
//       model: this.model,
//       prompt: prompt,
//       stream: false,
//     });
//     return { text: response.response };
//   }

//   async chat(params) {
//     const messages = params.messages || [];
//     const response = await this.ollama.chat({
//       model: this.model,
//       messages: messages,
//       stream: false,
//     });
//     return { message: { content: response.message.content } };
//   }
// }

// // Configure Settings
// Settings.embedModel = new OllamaEmbedding({
//   model: "nomic-embed-text",
//   baseUrl: OLLAMA_BASE_URL,
// });

// Settings.llm = new OllamaLLM({
//   model: "llama3.2",
//   config: {
//     host: OLLAMA_BASE_URL,
//   },
// });

// // AWS S3 Client
export const s3Client = new S3Client({
  credentials: {
    accessKeyId: process.env.AWS_S3_ID,
    secretAccessKey: process.env.AWS_SECRET,
  },
  region: process.env.AWS_REGION,
});

// async function downloadPdfFromS3(key) {
//   const command = new GetObjectCommand({
//     Bucket: process.env.AWS_S3_BUCKET_NAME,
//     Key: key,
//   });

//   const response = await s3Client.send(command);
  
//   const chunks = [];
//   for await (const chunk of response.Body) {
//     chunks.push(chunk);
//   }
//   const buffer = Buffer.concat(chunks);
//   return new Uint8Array(buffer);
// }

// async function extractPdfText(pdfBuffer) {
//   const pdf = await pdfjsLib.getDocument({ data: pdfBuffer }).promise;
//   let fullText = "";

//   for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
//     const page = await pdf.getPage(pageNum);
//     const content = await page.getTextContent();
//     const strings = content.items.map((item) => item.str).join(" ");
//     fullText += strings + "\n";
//   }

//   return fullText;
// }

// export async function createRagIndexFromPDFs(userId, pdfKeys) {
//   try {
//     const documents = [];

//     for (let key of pdfKeys) {
//       console.log(`Downloading PDF: ${key}`);
//       const pdfBuffer = await downloadPdfFromS3(key);
      
//       console.log(`Extracting text from PDF: ${key}`);
//       const text = await extractPdfText(pdfBuffer);
      
//       console.log(`PDF text length: ${text.length} characters`);
//       // documents.push(new Document({ text, metadata: { userId, pdfKey: key } }));
//       console.log("here is the extracted text",text)
//     }

//     // console.log(`Creating vector index for ${documents.length} documents...`);
//     // const index = await VectorStoreIndex.fromDocuments(documents);
    
//     console.log(`Index created successfully`);
//     // return index.toJSON();
//   } catch (error) {
//     console.error("Error in createRagIndexFromPDFs:", error);
//     throw error;
//   }
// }

// export async function loadIndexAndQuery(indexData, query) {
//   try {
//     console.log(`Loading index and querying: ${query}`);
//     const index = await VectorStoreIndex.fromJSON(indexData);
//     const queryEngine = index.asQueryEngine();
//     const response = await queryEngine.query({ query });
    
//     return response.toString();
//   } catch (error) {
//     console.error("Error in loadIndexAndQuery:", error);
//     throw error;
//   }
// }