import asyncHandler from "../utils/asyncHandler.js"
import axios from "axios"
import ragContext from "../models/ragContext.model.js"
import ApiError from "../utils/apiError.js"
import ApiResponse from "../utils/apiResponse.js"

const contextCache = new Map()
const rateLimit = new Map()

const CACHE_TTL = 15 * 60 * 1000
const MIN_INTERVAL = 2000
const MAX_CONTEXT_CHARS = 150000

const CEREBRAS_API_KEY = process.env.CEREBRAS_API_KEY

if (!CEREBRAS_API_KEY) {
  throw new Error("CEREBRAS_API_KEY missing in environment")
}

async function getContextForOrganisation(orgId) {
  const now = Date.now()
  const cached = contextCache.get(orgId)

  if (cached && now - cached.timestamp < CACHE_TTL) {
    return cached.data
  }

  const contexts = await ragContext
    .find({ organisationId: orgId })
    .select("uploadedDocuments.fileName uploadedDocuments.extractedText")
    .lean()

  let mergedText = ""

  for (const ctx of contexts) {
    for (const doc of ctx.uploadedDocuments || []) {
      if (doc?.extractedText) {
        mergedText += `\n\n${doc.fileName}:\n${doc.extractedText}`
      }
    }
  }

  if (!mergedText.trim()) {
    mergedText = "No institutional document context available."
  }

  if (mergedText.length > MAX_CONTEXT_CHARS) {
    mergedText = mergedText.slice(-MAX_CONTEXT_CHARS)
  }

  contextCache.set(orgId, {
    timestamp: now,
    data: mergedText
  })

  return mergedText
}

export const chatBot = asyncHandler(async (req, res) => {
  const message = req.body?.message

  if (typeof message !== "string" || !message.trim()) {
    throw new ApiError(400, "Invalid message")
  }

  const orgId = req.organisation?._id
  if (!orgId) {
    throw new ApiError(401, "Unauthorized")
  }

  const now = Date.now()
  const lastCall = rateLimit.get(orgId) || 0

  if (now - lastCall < MIN_INTERVAL) {
    throw new ApiError(429, "Too many requests. Please wait.")
  }

  rateLimit.set(orgId, now)

  const documentContext = await getContextForOrganisation(orgId)

  const prompt = `
You are the official AI assistant for Synchron and AiCrona.

Answer ONLY using the document context below.
If the answer is not found, say:
"I'm not able to find this information in your uploaded documents."

DOCUMENT CONTEXT:
${documentContext}

USER QUESTION:
${message.trim()}

RULES:
- No hallucination
- No assumptions
- Short, factual answer only

ANSWER:
`.trim()

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
        Authorization: `Bearer ${CEREBRAS_API_KEY}`,
        "Content-Type": "application/json"
      },
      timeout: 20000
    }
  )

  let reply = response?.data?.choices?.[0]?.message?.content
  reply = cleanResponse(reply)

  return res.json(
    new ApiResponse(200, {
      reply,
      contextUsed: true
    })
  )
})

function cleanResponse(text) {
  if (!text) return "No valid response."

  return text
    .replace(/undefined/gi, "")
    .replace(/\s+/g, " ")
    .trim()
}
