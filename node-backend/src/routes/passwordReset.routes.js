import { Router } from "express";
import {
  sendOtp,
  verifyOtp,
  resetPassword,
} from "../controllers/PasswordReset.controller.js";

const router = Router();

router.post("/forgot-password", sendOtp);
router.post("/verify-otp", verifyOtp);
router.post("/reset-password", resetPassword);

export default router;
