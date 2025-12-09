import { TimetableRequest } from "../models/timetableRequest.model.js";
import ApiError from "../utils/apiError.js";
import ApiResponse from "../utils/apiResponse.js";
import asyncHandler from "../utils/asyncHandler.js";
import { nanoid } from "nanoid";

export const createTimetableRequest = asyncHandler(async (req, res) => {
  const seneteId = req.senate?.senateId || nanoid()
  const organisationId = req.organisation?._id;
  const { year, course, semester, message } = req.body;
  if(!year || !course || !semester)
  {
    throw new ApiError(400,"Provide necessary feeilds")
  }
  if (!seneteId || !organisationId)
    throw new ApiError(401, "Senate login required");

  if (!year || !course || !semester)
    throw new ApiError(400, "Year, course, and semester are required");

  const request = await TimetableRequest.findOneAndUpdate(
    {
      seneteId,
      organisationId,
      year: year.trim().toLowerCase(),
      course: course.trim().toLowerCase(),
      semester: semester.trim().toLowerCase(),
    },
    {
      $set: {
        message: message || "Timetable for approval",
        status: "pending",
        reviewedBy: null,
      },
    },
    {
      new: true,
      upsert: true,
    }
  );

  return res
    .status(201)
    .json(new ApiResponse(201, request, "Timetable request submitted/updated"));
});



export const listTimetableRequests = asyncHandler(async (req, res) => {
  const organisationId = req.admin?.organisationId;

  if (!organisationId)
    throw new ApiError(401, "Admin login required");

  const requests = await TimetableRequest.find({ organisationId })
    .sort({ createdAt: -1 })
    .lean();

  return res
    .status(200)
    .json(new ApiResponse(200, requests, "Timetable requests fetched"));
});


export const approveTimetableRequest = asyncHandler(async (req, res) => {
  const adminId = req.admin?._id;
  const organisationId = req.admin?.organisationId;
  const { requestId } = req.params;

  if (!adminId || !organisationId)
    throw new ApiError(401, "Admin login required");

  const request = await TimetableRequest.findOneAndUpdate(
    { _id: requestId, organisationId },
    { status: "approved", reviewedBy: adminId },
    { new: true }
  );

  if (!request)
    throw new ApiError(404, "Timetable request not found");

  return res.status(200).json(
    new ApiResponse(200, request, "Timetable request approved")
  );
});

export const rejectTimetableRequest = asyncHandler(async (req, res) => {
  const adminId = req.admin?._id;
  const organisationId = req.admin?.organisationId;
  const { requestId } = req.params;

  if (!adminId || !organisationId)
    throw new ApiError(401, "Admin login required");

  const request = await TimetableRequest.findOneAndUpdate(
    { _id: requestId, organisationId },
    { status: "rejected", reviewedBy: adminId },
    { new: true }
  );

  if (!request)
    throw new ApiError(404, "Timetable request not found");

  return res.status(200).json(
    new ApiResponse(200, request, "Timetable request rejected")
  );
});


export const deleteTimetableRequest = asyncHandler(async (req, res) => {
  const organisationId = req.admin?.organisationId;
  const { requestId } = req.params;

  if (!organisationId)
    throw new ApiError(401, "Admin login required");

  const deleted = await TimetableRequest.findOneAndDelete({
    _id: requestId,
    organisationId
  });

  if (!deleted)
    throw new ApiError(404, "Timetable request not found or not allowed");

  return res
    .status(200)
    .json(new ApiResponse(200, null, "Timetable request deleted"));
});
