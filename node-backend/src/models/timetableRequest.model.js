import mongoose from "mongoose"

const timetableRequestSchema = new mongoose.Schema(
  {
    seneteId: {
      type: String,
      required: true,
    },
    year: {
      type: String,
      lowercase: true,
      trim: true,
      required: true,
    },
    course: {
      type: String,
      lowercase: true,
      trim: true,
      required: true,
    },
    semester: {
      type: String,
      lowercase: true,
      trim: true,
      required: true,
    },
    organisationId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Organisation",
      required: true,
    },
    message: {
      type: String,
      default: "Timetable for approval",
    },
    status: {
      type: String,
      enum: ["pending", "approved", "rejected"],
      default: "pending",
    },
    reviewedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Organisation",
      default: null,
    },
  },
  { timestamps: true }
);

timetableRequestSchema.index(
  { seneteId: 1, organisationId: 1, year: 1, course: 1, semester: 1 },
  { unique: true }
);

export const TimetableRequest = mongoose.model("TimetableRequest", timetableRequestSchema);
