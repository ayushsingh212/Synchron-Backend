import asyncHandler from "../utils/asyncHandler.js";
import axios from "axios";
import ragContext from "../models/ragContext.model.js";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import dotenv from "dotenv"

// -------------------------------
// IN-MEMORY CACHE
// -------------------------------
const contextCache = new Map();  
const rateLimit = new Map();     

const CEREBRAS_API_KEY=`csk-9m4jhn59dmk22fdpmdxxk96d2e4dd3ewwjevf5erry5dj89e`
// Cache Time = 15 minutes
const CACHE_TTL = 15 * 60 * 1000;
// Min time between chatbot requests = 2 seconds
const MIN_INTERVAL = 2000;


// ---------------------------------
// HELPER: GET OR BUILD CONTEXT
// ---------------------------------
async function getContextForOrganisation(orgId) {
  const now = Date.now();

  const cached = contextCache.get(orgId);
  if (cached && now - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const contexts = await ragContext.find({ organisationId: orgId }).lean();

  let mergedText = "";
  contexts.forEach(ctx => {
    ctx.uploadedDocuments.forEach(doc => {
      if (doc.extractedText) {
        mergedText += `\n\n${doc.fileName}:\n${doc.extractedText}`;
      }
    });
  });

  if (!mergedText.trim()) mergedText = "No institutional document context available.";

  // Cerebras supports large context — no need to slice aggressively  
  if (mergedText.length > 150000) {
    mergedText = mergedText.slice(-150000);  // keep last 150k chars
  }

  contextCache.set(orgId, {
    timestamp: now,
    data: mergedText
  });

  return mergedText;
}


// ---------------------------------
// MAIN CHATBOT CONTROLLER (CEREBRAS)
// ---------------------------------
export const chatBot = asyncHandler(async (req, res) => {
  const { message } = req.body;

  if (!message?.trim()) {
    return res.status(400).json({ success: false, reply: "Please provide a valid message." });
  }

  const orgId = req.organisation?._id;
  if (!orgId) {
    return res.status(401).json({ success: false, reply: "Please login first." });
  }


  // ---------------------------
  // RATE LIMITING (2 sec per org)
  // ---------------------------
  const lastCall = rateLimit.get(orgId) || 0;
  const now = Date.now();

  if (now - lastCall < MIN_INTERVAL) {
    return res.status(429).json({
      success: false,
      reply: "Please wait a moment before sending another message."
    });
  }
  rateLimit.set(orgId, now);


  // ---------------------------
  // GET RAG CONTEXT
  // ---------------------------
  const documentContext = await getContextForOrganisation(orgId);


  // -------------------------------
  // BUILD THE RAG PROMPT
  // -------------------------------
  const prompt = `
You are the official AI assistant for Synchron and AiCrona.

You MUST answer the user's question STRICTLY using the following institutional documents.
If answer is not in the context, say:
"I'm not able to find this information in your uploaded documents."

================ DOCUMENT CONTEXT START ================
${documentContext}
================ DOCUMENT CONTEXT END ==================

USER QUESTION:
${message.trim()}

Strict rules:
- Do NOT hallucinate
- Do NOT invent facts
- Use clean English
- No duplicate characters
- Keep answer short and accurate

FINAL ANSWER:
`;

  // -----------------------------------
  // CALL CEREBRAS API
  // -----------------------------------
  try {
    console.log("api",CEREBRAS_API_KEY)
    const response = await axios.post(
      "https://api.cerebras.ai/v1/chat/completions",
      {
        model: "gpt-oss-120b", 
        messages: [
          { role: "system", content: "You are a strict RAG assistant." },
          { role: "user", content: prompt }
        ],
        temperature: 0.2,
        max_tokens: 900
      },
      {
        headers: {
          "Authorization": `Bearer ${CEREBRAS_API_KEY}`,
          "Content-Type": "application/json"
        },
        timeout: 20000
      }
    );

    let reply = response.data?.choices?.[0]?.message?.content || "";
    reply = aggressiveCleanResponse(reply);

    return res.json({
      success: true,
      reply,
      contextUsed: true
    });

  } catch (err) {
    console.error("Cerebras Error:", err?.response?.data || err?.message);

    return res.status(500).json({
      success: false,
      reply: "I'm experiencing technical difficulties. Please try again shortly."
    });
  }
});


// -------------------------------------
// CLEAN DUPLICATION BUG
// -------------------------------------
function aggressiveCleanResponse(text) {
  if (!text) return "No valid response.";

  return text
    .replace(/undefined/gi, "")
    .replace(/([a-zA-Z])\1+/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}
