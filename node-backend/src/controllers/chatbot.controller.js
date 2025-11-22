import asyncHandler from "../utils/asyncHandler.js";
import axios from "axios";

export const chatBot = asyncHandler(async (req, res) => {
  const { message } = req.body;

  if (!message || message.trim() === "") {
    return res.status(400).json({ 
      success: false,
      reply: "Please provide a valid message." 
    });
  }

  try {
    const prompt =
      "You are the official AI assistant for Synchron and AiCrona platform.\n\n" +
      
      "## ABOUT SYNCHRON & AICRONA\n" +
      "- Synchron is the development team that created AiCrona\n" +
      "- AiCrona is an AI-powered university timetable scheduling platform\n" +
      "- Our mission is to simplify academic scheduling through artificial intelligence\n\n" +
      
      "## PLATFORM WORKFLOW & FEATURES\n" +
      "### 1. Organization Registration & Setup\n" +
      "- Educational institutions register and create admin accounts\n" +
      "- Admin accesses the Institution Dashboard after login\n" +
      "- Secure authentication and role-based access control\n\n" +
      
      "### 2. Academic Data Management\n" +
      "- In Academic Data Tab, admin selects: Course, Year, Semester for timetable generation\n" +
      "- Admin can add/manage: Courses, Years, Semesters, Subjects, Faculty, Sections\n" +
      "- Data Taker feature allows manual entry or PDF upload for bulk data\n" +
      "- System auto-parses PDF content and auto-fills information fields\n" +
      "- Data validation and duplicate prevention mechanisms\n\n" +
      
      "### 3. AI Timetable Generation\n" +
      "- Admin clicks 'Generate And Save Timetable' for specific course-year-semester\n" +
      "- AiCrona's AI engine generates 3 optimized timetable variants\n" +
      "- Optimization considers: Faculty availability, room capacity, subject priorities, time constraints\n" +
      "- Each variant shows section → faculty → room level details\n\n" +
      
      "### 4. Timetable Management\n" +
      "- Admin reviews and compares all 3 timetable variants\n" +
      "- Selects and approves the most suitable variant\n" +
      "- Approved timetable becomes the official schedule\n" +
      "- All generated timetables accessible in Timetable Manager tab\n" +
      "- Export capabilities to PDF and other formats\n\n" +
      
      "## RESPONSE GUIDELINES\n" +
      "1. Provide CLEAR, CONCISE, and WELL-FORMATTED responses\n" +
      "2. Use proper spacing and paragraph breaks for readability\n" +
      "3. Avoid any markdown formatting, code blocks, or special characters\n" +
      "4. Ensure responses are in perfect English without duplication or corruption\n" +
      "5. Be helpful, professional, and solution-oriented\n" +
      "6. If unsure about specific details, guide users to appropriate platform sections\n" +
      "7. For technical issues, provide step-by-step troubleshooting guidance\n" +
      "8. Always maintain a positive and supportive tone\n\n" +
      
      "## CURRENT USER QUERY\n" +
      "User Message: " + message.trim() + "\n\n" +
      
      "Please provide a helpful, accurate response that addresses the user's specific question about AiCrona platform features, workflow, or any issues they're experiencing.";

    const url = process.env.GEMINI_URL;
    
    if (!url) {
      console.error("Gemini URL not configured");
      return res.status(500).json({
        success: false,
        reply: "Service configuration error. Please contact support.",
        error: "GEMINI_URL environment variable not set"
      });
    }

    console.log("Sending request to Gemini API...");
    console.log("User Message:", message);
    console.log("Prompt Length:", prompt.length);

    const response = await axios.post(
      url,
      {
        contents: [{
          parts: [{ text: prompt }]
        }],
        generationConfig: {
          temperature: 0.7,
          topK: 40,
          topP: 0.95,
          maxOutputTokens: 1024,
        }
      },
      {
        timeout: 30000,
        headers: {
          'Content-Type': 'application/json',
        },
        validateStatus: function (status) {
          return status < 500; // Resolve only if status code < 500
        }
      }
    );

    console.log("Gemini API Response Status:", response.status);
    console.log("Gemini API Response Headers:", response.headers);

    // Enhanced response validation
    if (!response.data) {
      throw new Error("Empty response from Gemini API");
    }

    let reply;
    
    // Multiple response format handling
    if (response.data.candidates && 
        response.data.candidates[0] && 
        response.data.candidates[0].content && 
        response.data.candidates[0].content.parts && 
        response.data.candidates[0].content.parts[0] &&
        response.data.candidates[0].content.parts[0].text) {
      
      reply = response.data.candidates[0].content.parts[0].text;
    
    } else if (response.data.choices && 
               response.data.choices[0] && 
               response.data.choices[0].message && 
               response.data.choices[0].message.content) {
      
      reply = response.data.choices[0].message.content;
    
    } else if (response.data.text) {
      
      reply = response.data.text;
    
    } else {
      console.error("Unexpected Gemini response format:", JSON.stringify(response.data, null, 2));
      throw new Error("Unexpected response format from Gemini API");
    }

    // Comprehensive response cleaning
    const cleanReply = cleanGeminiResponse(reply);
    
    console.log("Original Reply Length:", reply.length);
    console.log("Cleaned Reply Length:", cleanReply.length);
    console.log("Original Reply Preview:", reply.substring(0, 200));
    console.log("Cleaned Reply Preview:", cleanReply.substring(0, 200));

    if (!cleanReply || cleanReply.trim().length < 2) {
      throw new Error("Cleaned response is empty or too short");
    }

    res.json({ 
      success: true,
      reply: cleanReply,
      metadata: {
        originalLength: reply.length,
        cleanedLength: cleanReply.length,
        timestamp: new Date().toISOString()
      }
    });

  } catch (err) {
    console.error("ChatBot Error Details:", {
      name: err.name,
      message: err.message,
      stack: err.stack,
      response: err.response?.data,
      status: err.response?.status,
      code: err.code
    });

    // User-friendly error messages based on error type
    let userMessage = "I'm experiencing technical difficulties. Please try again in a moment.";
    let statusCode = 500;

    if (err.response?.status === 429) {
      userMessage = "I'm currently processing too many requests. Please wait a moment and try again.";
      statusCode = 429;
    } else if (err.response?.status === 400) {
      userMessage = "There was an issue with the request. Please check your input and try again.";
      statusCode = 400;
    } else if (err.code === 'ECONNABORTED') {
      userMessage = "The request took too long to process. Please try again.";
      statusCode = 408;
    } else if (err.code === 'ENOTFOUND' || err.code === 'ECONNREFUSED') {
      userMessage = "Service is temporarily unavailable. Please try again later.";
      statusCode = 503;
    }

    res.status(statusCode).json({ 
      success: false,
      reply: userMessage,
      error: process.env.NODE_ENV === 'development' ? err.message : undefined,
      timestamp: new Date().toISOString()
    });
  }
});

// Enhanced response cleaning function
function cleanGeminiResponse(text) {
  if (!text || typeof text !== "string") {
    return "I apologize, but I'm having trouble generating a response. Please try again.";
  }

  let cleaned = text;

  // Remove undefined strings (case insensitive)
  cleaned = cleaned.replace(/undefined/gi, '');
  
  // Fix character duplication issues (hheelllloo -> hello)
  cleaned = cleaned.replace(/([a-zA-Z])\1+/g, '$1');
  
  // Fix specific duplication patterns
  cleaned = cleaned.replace(/(\w)\1\1\1/g, '$1$1'); // aaaa -> aa
  cleaned = cleaned.replace(/(\w)\1/g, '$1');        // aa -> a
  
  // Remove multiple consecutive spaces
  cleaned = cleaned.replace(/\s+/g, ' ');
  
  // Remove any special character artifacts
  cleaned = cleaned.replace(/[�]/g, '');
  
  // Clean up common AI response artifacts
  cleaned = cleaned.replace(/�+/g, '');
  cleaned = cleaned.replace(/\[.*?\]/g, ''); // Remove [something] patterns
  cleaned = cleaned.replace(/\(.*?\)/g, ' '); // Clean parentheses content with space
  
  // Ensure proper sentence spacing
  cleaned = cleaned.replace(/\.([a-zA-Z])/g, '. $1');
  
  // Trim and final cleanup
  cleaned = cleaned.trim();
  
  // Capitalize first letter if needed
  if (cleaned.length > 0) {
    cleaned = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  }

  // Final validation
  if (cleaned.length < 2) {
    return "I apologize, but I couldn't generate a proper response. Please rephrase your question and try again.";
  }

  return cleaned;
}