import {Router} from "express"
import { chatBot } from "../controllers/chatbot.controller.js";








const router = Router()







router.get("/chat",chatBot)

export default router;