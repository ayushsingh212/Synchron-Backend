import mongoose from 'mongoose';
const { Schema } = mongoose;

const timeslotSchema = new Schema(
  {
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: 'Organisation',
      required: true
    },
    day: { type: Number, required: true }, 
    startTime: { type: String, required: true }, 
    endTime: { type: String, required: true } 
  },
  { timestamps: true }
);

export const Timeslot = mongoose.model('Timeslot', timeslotSchema);
