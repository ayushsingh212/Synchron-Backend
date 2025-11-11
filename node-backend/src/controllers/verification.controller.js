import asyncHandler from "../utils/asyncHandler.js";
import { redisClient } from "../middlewares/otp.middleware.js";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import bcrypt from "bcrypt";
import { sendEmail } from "../utils/sendMail.js";

// OTP Configuration
const OTP_EXPIRY = 5 * 60; // 5 minutes
const RATE_LIMIT = 100;    // max OTPs per hour
const RESEND_LIMIT = 60;   // resend cooldown in seconds

// Generate 6-digit OTP
export const generateOTP = () => Math.floor(100000 + Math.random() * 900000).toString();

// Verify OTP
export const verifyOtp = async (organisationEmail, otp) => {
  const hashedOtp = await redisClient.get(`otp:data:${organisationEmail}`);
  if (!hashedOtp) return false;
  return await bcrypt.compare(otp, hashedOtp);
};

// Send OTP
export const sendOTP = asyncHandler(async (req, res) => {
  const organisationEmail = req.body?.organisationEmail || req.user?.organisationEmail;

  if (!organisationEmail) {
    throw new ApiError(400, "organisationEmail is required");
  }

  if (!/^\S+@\S+\.\S+$/.test(organisationEmail)) {
    throw new ApiError(400, "Please provide a valid organisationEmail");
  }

  const now = Date.now();

  // 1️⃣ Resend cooldown
  const lastSent = await redisClient.get(`otp:lastSent:${organisationEmail}`);
  if (lastSent && now - parseInt(lastSent) < RESEND_LIMIT * 1000) {
    throw new ApiError(429, `Please wait ${RESEND_LIMIT} seconds before requesting another OTP.`);
  }

  // 2️⃣ Rate limit per hour
  const sentCount = await redisClient.get(`otp:count:${organisationEmail}`);
  if (sentCount && parseInt(sentCount) >= RATE_LIMIT) {
    throw new ApiError(429, "OTP limit exceeded. Try again after 1 hour.");
  }

  // 3️⃣ Generate and hash OTP
  const otp = generateOTP();
  const hashedOtp = await bcrypt.hash(otp, 10);

  // 4️⃣ Store OTP in Redis
  await redisClient.set(`otp:data:${organisationEmail}`, hashedOtp, { EX: OTP_EXPIRY });

  // 5️⃣ Update last sent time
  await redisClient.set(`otp:lastSent:${organisationEmail}`, now.toString(), { EX: RESEND_LIMIT });

  // 6️⃣ Update OTP request count
  const isNewKey = !sentCount;
  await redisClient.incr(`otp:count:${organisationEmail}`);
  if (isNewKey) await redisClient.expire(`otp:count:${organisationEmail}`, 3600); // 1 hour

  // 7️⃣ Send OTP email
  await sendEmail(
    organisationEmail,
    "Your OTP for Organisation Verification",
    `Your OTP is: ${otp}. It expires in 5 minutes.`
  );

  return res.status(202).json(new ApiResponse(200, {}, "OTP has been sent successfully"));
});

// Check OTP
export const checkOtp = asyncHandler(async (req, res) => {
  const { organisationEmail, otp } = req.body;

  if (!organisationEmail || !otp) {
    throw new ApiError(400, "Please provide both organisationEmail and OTP");
  }

  if (!/^\S+@\S+\.\S+$/.test(organisationEmail)) {
    throw new ApiError(400, "Please provide a valid organisationEmail");
  }

  const isCorrect = await verifyOtp(organisationEmail, otp);

  return res.status(200).json(new ApiResponse(200, { isCorrect }, "OTP verification result"));
});
