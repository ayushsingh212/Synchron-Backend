import asyncHandler from "../utils/asyncHandler.js";
import { redisClient } from "../middlewares/otp.middleware.js";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import bcrypt from "bcrypt";
import { sendEmail } from "../utils/sendMail.js";

// OTP Generator
export const generateOTP = () => Math.floor(100000 + Math.random() * 900000).toString();

const verifyOtp = async (organisationEmail, otp) => {
  console.log("I have been hitted verify");

  const hashedOtp = await redisClient.get(`otp:data:${organisationEmail}`);
  if (!hashedOtp) return false;

  const isOtpCorrect = await bcrypt.compare(otp, hashedOtp);
  return isOtpCorrect;
};

const sendOTP = asyncHandler(async (req, res) => {
  const OTP_EXPIRY = 5 * 60; 
  const RATE_LIMIT = 100;      
  const RESEND_LIMIT = 60;   
  const organisationEmail = req.body?.organisationEmail || req.user?.organisationEmail;
  console.log("I have been hitted orgEm",organisationEmail)
  if (!organisationEmail) {
    throw new ApiError(400, "organisationEmail is required");
  }

  const now = Date.now();

  // 1. Resend cooldown check
  const lastSent = await redisClient.get(`otp:lastSent:${organisationEmail}`);
  if (lastSent && now - parseInt(lastSent) < RESEND_LIMIT * 1000) {
    throw new ApiError(429, "Please wait before requesting another OTP.");
  }

  // 2. Rate limit per hour
  const sentCount = await redisClient.get(`otp:count:${organisationEmail}`);
  if (sentCount && parseInt(sentCount) >= RATE_LIMIT) {
    throw new ApiError(429, "OTP limit exceeded. Try again after 1 hour.");
  }

  // 3. Generate and hash OTP
  const otp = generateOTP();
  const hashedOtp = await bcrypt.hash(otp, 10);

  await redisClient.set(`otp:data:${organisationEmail}`, hashedOtp, { ex: OTP_EXPIRY });

  await redisClient.set(`otp:lastSent:${organisationEmail}`, now.toString(), { ex: RESEND_LIMIT });

  // 6. Track OTP request count (increment + set expiry)
  await redisClient.incr(`otp:count:${organisationEmail}`);
  await redisClient.expire(`otp:count:${organisationEmail}`, 10); // expire in 1 hour

  // 7. Send organisationEmail
  await sendEmail(organisationEmail, "Your OTP for organisationEmail Verification", `Your OTP is: ${otp}`);

  // 8. Respond
  return res.status(202).json(
    new ApiResponse(200, {}, "OTP has been sent successfully")
  );
});
const checkOtp = asyncHandler(async(req,res)=>{


  const {organisationEmail,otp} = req.body 

if(!/^\S+@\S+\.\S+$/.test(organisationEmail))
{
   throw new ApiError(400,"Please provide a valid organisationEmail")

}

  if(!otp)
  {
    throw new ApiError(400,"Please provide the organisationEmail and the otp")
  }

 const isCorrect = await verifyOtp(organisationEmail,otp)







console.log(isCorrect)



return res.status(200)
.json(
  new ApiResponse(200,{isCorrect},"Otp checked ")
)






})

export { sendOTP,verifyOtp, checkOtp};
