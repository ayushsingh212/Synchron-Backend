import { Organisation } from "../models/organisation.model.js";
import bcrypt from "bcrypt";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import asyncHandler from "../utils/asyncHandler.js";

export const createSenate = asyncHandler(async (req, res) => {
  const { organisationId } = req.user;
  const { senateId, password } = req.body;

  if (!senateId || !password) throw new ApiError(400, "Senate fields missing");

  const org = await Organisation.findById(organisationId);
  if (!org) throw new ApiError(404, "Organisation not found");

  const exists = org.senates.find(s => s.senateId === senateId);
  if (exists) throw new ApiError(400, "Senate already exists");

  const hashed = await bcrypt.hash(password, 10);

  org.senates.push({
    organisationId,
    senateId,
    password: hashed
  });

  await org.save();

  return res
    .status(201)
    .json(new ApiResponse(201, org.senates, "Senate created"));
});

export const removeSenate = asyncHandler(async (req, res) => {
  const { organisationId } = req.user;
  const { senateId } = req.params;

  const org = await Organisation.findById(organisationId);
  if (!org) throw new ApiError(404, "Organisation not found");

  const initialLength = org.senates.length;

  org.senates = org.senates.filter(s => s.senateId !== senateId);

  if (org.senates.length === initialLength)
    throw new ApiError(404, "Senate not found");

  await org.save();

  return res
    .status(200)
    .json(new ApiResponse(200, org.senates, "Senate removed"));
});
export const listSenates = asyncHandler(async (req, res) => {
  const { organisationId } = req.user; 
  const org = await Organisation.findById(organisationId);
  if (!org) throw new ApiError(404, "Organisation not found");
  return res
    .status(200)
    .json(new ApiResponse(200, org.senates, "Senates retrieved"));
});