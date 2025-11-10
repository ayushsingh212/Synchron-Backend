import mongoose from 'mongoose';
const { Schema } = mongoose;

const roomSchema = new Schema(
  {
    organisationId: {
      type: Schema.Types.ObjectId,
      ref: 'Organisation',
      required: true
    },
    name: { type: String, required: true },
    capacity: { type: Number, default: 60 },
    type: { type: String, enum: ['classroom', 'lab'], default: 'classroom' }
  },
  { timestamps: true }
);

export const Room = mongoose.model('Room', roomSchema);
