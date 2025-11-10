import mongoose from 'mongoose';
const { Schema } = mongoose;

const timeslotSchema = new Schema(
  {
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: 'Organisation',
      required: true
    },
    day: { type: Number, required: true }, // 0..6 (Mon..Sun) - use 0..4 for Mon-Fri
    startTime: { type: String, required: true }, // "09:00"
    endTime: { type: String, required: true }   // "10:00"
  },
  { timestamps: true }
);

export const Timeslot = mongoose.model('Timeslot', timeslotSchema);
