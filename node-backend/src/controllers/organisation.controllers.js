
import asyncHandler from "../utils/asyncHandler.js";
import { Organisation } from "../models/organisation.model.js";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import bcrypt from "bcrypt";
import jwt from "jsonwebtoken";
import { redisClient } from "../middlewares/otp.middleware.js";
import { verifyOtp } from "./verification.controller.js";
import { options } from "../middlewares/auth.middleware.js";
import { uploadOnCloudinary, deleteFromCloudinary } from "../utils/cloudinary.js";

import { TimetableRequest } from "../models/timetableRequest.model.js";
import { z } from "zod";


const noEmoji = (s) => {
  try {
    if (typeof s !== "string") return true;
    return !/\p{Extended_Pictographic}/u.test(s);
  } catch (e) {
    return true;
  }
};

const objectIdPattern = /^[0-9a-fA-F]{24}$/;

const registerSchema = z.object({
  organisationName: z
    .string()
    .min(3, "organisationName must be at least 3 characters")
    .max(100, "organisationName too long")
    .refine(noEmoji, { message: "organisationName must not contain emoji or pictographic characters" }),
  organisationEmail: z.string().email("Invalid email").max(254),
  password: z.string().min(8, "Password must be at least 8 characters").max(128),
  organisationContactNumber: z.string().regex(/^\d{10}$/, "Contact number must be 10 digits"),
});

const verifyEmailParamsSchema = z.object({ organisationEmail: z.string().email() });
const verifyEmailBodySchema = z.object({ otp: z.string().min(4).max(6).regex(/^\d+$/, "OTP must be numeric") });

const loginWithOtpSchema = z.object({ organisationEmail: z.string().email(), otp: z.string().min(4).max(6).regex(/^\d+$/) });
const loginWithPasswordSchema = z.object({ organisationEmailOrorganisationContactNumber: z.string().min(3), password: z.string().min(8) });

const updateProfileSchema = z.object({
  organisationName: z.string().min(3).max(100).optional().refine((v) => (v ? noEmoji(v) : true), { message: "organisationName must not contain emoji" }),
  organisationEmail: z.string().email().optional(),
  otp: z.string().min(4).max(6).optional(),
  organisationContactNumber: z.string().regex(/^\d{10}$/, "Contact number must be 10 digits").optional(),
});

const changePasswordSchema = z.object({ oldPassword: z.string().min(1), newPassword: z.string().min(8).max(128) });

const idParamSchema = z.object({ id: z.string().regex(objectIdPattern, "Invalid id") });


const validateOrThrow = (schema, data) => {
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    const first = parsed.error?.errors?.[0];
    throw new ApiError(400, first?.message || "Validation failed", parsed.error.errors || []);
  }
  return parsed.data;
};


export const generateAccessAndRefreshToken = async (organisationId) => {
  const organisation = await Organisation.findById(organisationId);
  if (!organisation) throw new ApiError(404, "Organisation not found");

  const refreshToken = organisation.generateRefreshToken();
  const accessToken = organisation.generateAccessToken();

  organisation.refreshToken = refreshToken;
  await organisation.save({ validateBeforeSave: false });

  return { refreshToken, accessToken };
};





const registerOrganisation = asyncHandler(async (req, res) => {
  validateOrThrow(registerSchema, req.body);

  const { organisationName, organisationEmail, password, organisationContactNumber } = req.body;

  const existingOrganisation = await Organisation.findOne({
    $or: [{ organisationEmail }, { organisationContactNumber }],
  });

  if (existingOrganisation && existingOrganisation.isEmailVerified === true) {
    throw new ApiError(409, "Organisation with this email or contact number already exists");
  }

  if (existingOrganisation && existingOrganisation.isEmailVerified !== true) {
    await Organisation.deleteOne({ organisationEmail });
  }

  const avatarLocalPath = req?.file?.path;
  // if (!avatarLocalPath) throw new ApiError(400, "Avatar file is required");
   let avatar;
  if(avatarLocalPath){
  avatar = await uploadOnCloudinary(avatarLocalPath);
  if (!avatar) throw new ApiError(500, "Failed to upload avatar");
  }
 

  const organisation = await Organisation.create({
    organisationName,
    organisationEmail,
    password,
    organisationContactNumber,
    avatar: avatar?.url || "http",
  });

  const organisationObj = organisation.toObject ? organisation.toObject() : { ...organisation };
  delete organisationObj.password;
  delete organisationObj.refreshToken;

  return res.status(201).json(new ApiResponse(201, organisationObj, "Organisation registered successfully"));
});


const verifyOrganisationEmail = asyncHandler(async (req, res) => {
  validateOrThrow(verifyEmailParamsSchema, req.params);
  validateOrThrow(verifyEmailBodySchema, req.body);

  const { organisationEmail } = req.params;
  const { otp } = req.body;

  const isOtpCorrect = await verifyOtp(organisationEmail, otp, "register");
  if (!isOtpCorrect) throw new ApiError(400, "OTP incorrect");

  const org = await Organisation.findOne({ organisationEmail });
  if (!org) throw new ApiError(404, "Organisation not found");

  org.isEmailVerified = true;
  await org.save();

  const {accessToken,refreshToken} = await generateAccessAndRefreshToken(org._id);
    const adminToken = org.generateAdminToken();
  return res.status(200).cookie("adminToken",adminToken,options).cookie("accessToken",accessToken,options).cookie("refreshToken",refreshToken,options).json(new ApiResponse(200, {}, "Email verified successfully"));
});


const loginOrganisation = asyncHandler(async (req, res) => {
  const { otp, organisationEmailOrorganisationContactNumber, password, organisationEmail } = req.body;

  let organisation;

  if (otp) {
    validateOrThrow(loginWithOtpSchema, { organisationEmail, otp });

    organisation = await Organisation.findOne({ organisationEmail, isEmailVerified: true });
    if (!organisation) throw new ApiError(404, "Organisation not found");

    const otpVerified = await verifyOtp(organisationEmail, otp,"login");
    if (!otpVerified) throw new ApiError(400, "Invalid OTP");
  } else {
    validateOrThrow(loginWithPasswordSchema, { organisationEmailOrorganisationContactNumber, password });

    if (!organisationEmailOrorganisationContactNumber || !password) {
      throw new ApiError(400, "Email/contact number and password are required");
    }

    let query = {};
    if (/^\d{10}$/.test(organisationEmailOrorganisationContactNumber.trim())) {
      query.organisationContactNumber = organisationEmailOrorganisationContactNumber.trim();
    } else {
      query.organisationEmail = organisationEmailOrorganisationContactNumber.trim().toLowerCase();
    }
    query.isEmailVerified = true;

    organisation = await Organisation.findOne(query).select("+password");
    if (!organisation) throw new ApiError(404, "Organisation not found");

    const isPasswordCorrect = await organisation.isPasswordCorrect(password);
    if (!isPasswordCorrect) throw new ApiError(401, "Incorrect password");
  }

  const { refreshToken, accessToken } = await generateAccessAndRefreshToken(organisation._id);
  const safeOrganisation = await Organisation.findById(organisation._id).select("-password -refreshToken");

  const adminToken = organisation.generateAdminToken()
  return res
    .status(200)
    .cookie("refreshToken", refreshToken, options)
    .cookie("accessToken", accessToken, options)
    .cookie("adminToken",adminToken,options)
    .json(new ApiResponse(200, safeOrganisation, "Login successful"));
});


const logoutOrganisation = asyncHandler(async (req, res) => {
  const organisationId = req.organisation?._id;
  if (!organisationId) return res.status(200).json(new ApiResponse(200, {}, "Already logged out"));

  await Organisation.findByIdAndUpdate(organisationId, { refreshToken: undefined });

  return res
    .status(202)
    .clearCookie("accessToken", options)
    .clearCookie("refreshToken", options)
    .clearCookie("adminToken",options)
    .clearCookie("senateToken",options)
    .json(new ApiResponse(200, {}, "Organisation logged out successfully"));
});


const updateProfile = asyncHandler(async (req, res) => {
  const organisationId = req.organisation?._id;
  if (!organisationId) throw new ApiError(401, "Login First");

  const validated = validateOrThrow(updateProfileSchema, req.body);

  const { organisationName, organisationEmail, otp, organisationContactNumber } = validated;
  const updates = {};

  if (organisationName?.trim()) updates.organisationName = organisationName.trim();
  if (/^\d{10}$/.test(organisationContactNumber || "")) updates.organisationContactNumber = organisationContactNumber;

  if (organisationEmail) {
    if (!otp) throw new ApiError(400, "OTP required to update email");

    const hashedOtp = await redisClient.get(`otp:data:${organisationEmail}`);
    if (!hashedOtp) throw new ApiError(404, "OTP expired or not found");

    const isVerified = await bcrypt.compare(otp, hashedOtp);
    if (!isVerified) throw new ApiError(400, "Email not verified by OTP");

    updates.organisationEmail = organisationEmail;
  }

  const updatedOrganisation = await Organisation.findByIdAndUpdate(organisationId, updates, {
    new: true,
    runValidators: true,
  }).select("-password -refreshToken");

  return res.status(200).json(new ApiResponse(200, updatedOrganisation, "Profile updated successfully"));
});


const changePassword = asyncHandler(async (req, res) => {
  validateOrThrow(changePasswordSchema, req.body);

  const organisationId = req.organisation?._id;
  if (!organisationId) throw new ApiError(401, "Login First");

  const { oldPassword, newPassword } = req.body;

  const organisation = await Organisation.findById(organisationId).select("+password");
  if (!organisation) throw new ApiError(404, "Organisation not found");

  const isMatch = await organisation.isPasswordCorrect(oldPassword);
  if (!isMatch) throw new ApiError(401, "Old password is incorrect");

  organisation.password = newPassword;
  await organisation.save();

  return res.status(200).json(new ApiResponse(200, {}, "Password changed successfully"));
});


const updateAvatar = asyncHandler(async (req, res) => {
  const organisationId = req.organisation?._id;
  if (!organisationId) throw new ApiError(401, "Login First");

  const organisation = await Organisation.findById(organisationId);
  if (!organisation) throw new ApiError(404, "Organisation not found");

  const avatarLocalPath = req.file?.path || req.files?.avatar?.[0]?.path;
  if (!avatarLocalPath) throw new ApiError(400, "Avatar file is required");

  if (organisation.avatar) {
    try {
      await deleteFromCloudinary(organisation.avatar);
    } catch (err) {
      console.warn("Failed to delete old avatar:", err?.message || err);
    }
  }

  const avatar = await uploadOnCloudinary(avatarLocalPath);
  if (!avatar) throw new ApiError(500, "Avatar upload failed");

  organisation.avatar = avatar.url;
  await organisation.save();

  return res.status(200).json(new ApiResponse(200, { avatar: avatar.url }, "Avatar updated successfully"));
});


const deleteOrganisation = asyncHandler(async (req, res) => {
  const organisationId = req.organisation?._id;
  if (!organisationId) throw new ApiError(401, "Login First");

  const organisation = await Organisation.findById(organisationId);
  if (!organisation) throw new ApiError(404, "Organisation not found");

  if (organisation.avatar) {
    try {
      await deleteFromCloudinary(organisation.avatar);
    } catch (err) {
      console.warn("Failed to delete avatar from cloud:", err?.message || err);
    }
  }

  await Organisation.findByIdAndDelete(organisationId);

  return res.status(200).json(new ApiResponse(200, {}, "Organisation deleted successfully"));
});


const refreshAccessToken = asyncHandler(async (req, res) => {
  const token = req.cookies?.refreshToken;
  if (!token) throw new ApiError(400, "Refresh token missing");

  let decoded;
  try {
    decoded = jwt.verify(token, process.env.REFRESH_TOKEN_SECRET);
  } catch (err) {
    throw new ApiError(401, "Invalid refresh token");
  }

  const organisation = await Organisation.findById(decoded._id);
  if (!organisation) throw new ApiError(404, "Organisation not found");
  if (organisation.refreshToken !== token) throw new ApiError(403, "Refresh token mismatch");

  const { accessToken, refreshToken } = await generateAccessAndRefreshToken(organisation._id);

  return res
    .status(200)
    .cookie("accessToken", accessToken, options)
    .cookie("refreshToken", refreshToken, options)
    .json(new ApiResponse(200, { accessToken, refreshToken }, "Token refreshed"));
});


const getCurrentOrganisation = asyncHandler(async (req, res) => {
  const organisationId = req.organisation?._id;
  if (!organisationId) throw new ApiError(401, "Login First");

  const organisation = await Organisation.findById(organisationId).select("-password -refreshToken");

  return res.status(200).json(new ApiResponse(200, organisation, "Organisation fetched successfully"));
});


 const getAllOrganisation = asyncHandler(async (req, res) => {
  const organisations = await Organisation.find({}).select("-password");
  if (!organisations || organisations.length === 0) {
    throw new ApiError(404, "No organisation exist");
  }

  return res.status(200).json(new ApiResponse(200, organisations, "Data fetched successfully"));
});



export {
  registerOrganisation,
  loginOrganisation,
  logoutOrganisation,
  refreshAccessToken,
  getCurrentOrganisation,
  updateProfile,
  changePassword,
  updateAvatar,
  deleteOrganisation,
  verifyOrganisationEmail,
  getAllOrganisation,

};
