import { Organisation } from "../models/organisation.model.js";
import bcrypt from "bcrypt";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import asyncHandler from "../utils/asyncHandler.js";
import { options } from "../middlewares/auth.middleware.js";
import { generateAccessAndRefreshToken } from "./organisation.controllers.js";

export const senateLogin = asyncHandler(async (req, res) => {
  const { organisationEmail, senateId, password } = req.body;

  if (!organisationEmail || !senateId || !password)
    throw new ApiError(400, "Missing fields");

  const org = await Organisation.findOne({ organisationEmail });
  if (!org) throw new ApiError(404, "Organisation not found");

  const senate = org.senates.find(s => s.senateId === senateId);
  if (!senate) throw new ApiError(401, "Invalid credentials");

  const match = await bcrypt.compare(password, senate.password);
  if (!match) throw new ApiError(401, "Invalid credentials");

  const senateToken = org.generateSenateToken(senateId);

  const { refreshToken, accessToken } = await generateAccessAndRefreshToken(organisation._id);  return res
    .status(200)
    .cookie("senateToken", senateToken,options)
    .cookie("refreshToken",refreshToken,options)
    .cookie("accessToken",accessToken,options)
    .json(
      new ApiResponse(200, {
        organisationId: org._id,
        senateId,
        senateToken
      }, "Senate login successful")
    );
});
