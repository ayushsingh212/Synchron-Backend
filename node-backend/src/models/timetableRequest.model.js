import mongoose, { Schema } from "mongoose";

const timetableRequestSchema = new Schema(
  {
    seneteId: {
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

      default:"Timetable for approval" 
    },
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
