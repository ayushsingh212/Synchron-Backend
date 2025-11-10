import mongoose, { Schema } from "mongoose";

const timetableRequestSchema = new Schema(
  {
    facultyId: {
      type: Schema.Types.ObjectId,
      ref: "Faculty",
      required: true,
    },
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: "Organisation",
      required: true,
    },
    message: {
      type: String,
      required: true,
      trim: true,
    },
    preferredSlots: [
      {
        day: String,
        timeSlot: String,
      },
    ],
    status: {
      type: String,
      enum: ["pending", "approved", "rejected"],
      default: "pending",
    },
    reviewedBy: {
      type: Schema.Types.ObjectId,
      ref: "Organisation",
    },
  },
  { timestamps: true }
);

export const TimetableRequest = mongoose.model("TimetableRequest", timetableRequestSchema);
