import {Router} from "express"
import { chatBot } from "../controllers/chatbot.controller.js";
import { verifyJWT } from "../middlewares/auth.middleware.js";








const router = Router()
router.post("/chat",verifyJWT,chatBot)

export default router;