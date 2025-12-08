import mongoose from "mongoose";

const ragContextSchema = new mongoose.Schema(
  {
    organisationId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true
    },

    folderName: {
      type: String,
      trim: true,
      required: true
    },

    uploadedDocuments: [
      {
        fileName: String,
        key: String,
        viewUrl: String,
        extractedText: String,
        vectorId: String
      }
    ]
  },
  { timestamps: true }
);

ragContextSchema.index(
  { organisationId: 1, folderName: 1 },
  { unique: true }
);

export default mongoose.model("ragContext", ragContextSchema);
