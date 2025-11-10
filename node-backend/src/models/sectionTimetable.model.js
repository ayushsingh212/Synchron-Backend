import mongoose, { Schema } from "mongoose";

const SectionTimetableSchema = new Schema(
  { 
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: "Organisation",
      required: true,
    },
    section_id: { type: String, required: true },  // no `unique: true` here
    section_name: { type: String },
    semester: { type: Number },
    specialization: { type: String, default: "" },

    // periods: store as Map (period -> time string)
    periods: { type: Map, of: String },

    // timetable is nested day -> period -> {faculty, room, subject, type} OR string like "FREE"
    timetable: { type: Schema.Types.Mixed },
  },
  { timestamps: true }
);

// ✅ Ensure uniqueness only within an organisation
SectionTimetableSchema.index(
  { section_id: 1, organisationId: 1 },
  { unique: true }
);

export const SectionTimetable = mongoose.model(
  "SectionTimetable",
  SectionTimetableSchema
);
