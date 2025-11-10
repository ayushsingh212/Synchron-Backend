import mongoose from "mongoose";
const { Schema } = mongoose;

const timetableEntry = new Schema(
  {
    courseId: { type: Schema.Types.ObjectId, ref: "Course" },
    subjectId: { type: Schema.Types.ObjectId, ref: "Subject" },
    facultyId: { type: Schema.Types.ObjectId, ref: "Faculty" },
    roomId: { type: Schema.Types.ObjectId, ref: "Room" },
    timeslot: {
      day: Number,
      slot: Number,
      timeslotId: { type: Schema.Types.ObjectId, ref: "Timeslot" },
    },
  },
  { _id: false }
);

const timetableSchema = new Schema(
  {
    organisationId: { type: Schema.Types.ObjectId, ref: "Organisation", required: true },
    name: { type: String },
    generatedAt: { type: Date, default: Date.now },
    entries: [timetableEntry],
    status: { type: String, enum: ["draft", "submitted", "approved"], default: "draft" },
  },
  { timestamps: true }
);

export const Timetable = mongoose.model("Timetable", timetableSchema);
