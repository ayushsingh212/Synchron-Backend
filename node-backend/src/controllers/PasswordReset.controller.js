import { Organisation } from "../models/organisation.model.js";
import { sendEmail } from "../utils/sendMail.js";
import bcrypt from "bcryptjs";

const sendOtp = async (req, res) => {
  try {
    const { organisationEmail } = req.body;

    const org = await Organisation.findOne({ organisationEmail });
    if (!org) return res.status(404).json({ message: "Email not found" });

    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    const expiry = Date.now() + 5 * 60 * 1000;

    org.otp = otp;
    org.otpExpiry = expiry;
    await org.save();

    await sendEmail(
      organisationEmail,
      "Password Reset OTP",
      `Your OTP is: ${otp}`,
      "Password Reset"
    );

    return res.status(200).json({ message: "OTP sent successfully" });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};

const verifyOtp = async (req, res) => {
  try {
    const { organisationEmail, otp } = req.body;

    const org = await Organisation.findOne({ organisationEmail });
    if (!org) return res.status(404).json({ message: "Email not found" });

    if (!org.otp || org.otp !== otp)
      return res.status(400).json({ message: "Invalid OTP" });

    if (org.otpExpiry < Date.now())
      return res.status(400).json({ message: "OTP expired" });

    return res.status(200).json({ message: "OTP verified successfully" });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};

const resetPassword = async (req, res) => {
  try {
    const { organisationEmail, newPassword } = req.body;

    const org = await Organisation.findOne({ organisationEmail }).select(
      "+password"
    );
    if (!org) return res.status(404).json({ message: "Email not found" });

    const hashed = await bcrypt.hash(newPassword, 10);
    org.password = hashed;

    org.otp = null;
    org.otpExpiry = null;

    await org.save();

    return res.status(200).json({ message: "Password reset successful" });
  } catch (error) {
    return res.status(500).json({ error: error.message });
  }
};

export { sendOtp, verifyOtp, resetPassword };
