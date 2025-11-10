import { Timeslot } from "../models/timeslot.model.js";

/**
 * Create a new timeslot
 */
export const createTimeslot = async (req, res) => {
  try {
    const { organisationId, day, startTime, endTime } = req.body;

    if (!organisationId || day === undefined || !startTime || !endTime) {
      return res.status(400).json({ success: false, message: "All fields are required" });
    }

    const timeslot = new Timeslot({ organisationId, day, startTime, endTime });
    await timeslot.save();

    res.status(201).json({ success: true, data: timeslot });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

/**
 * Get all timeslots for an organisation
 */
export const getTimeslotsByOrganisation = async (req, res) => {
  try {
    const { organisationId } = req.params;
    const timeslots = await Timeslot.find({ organisationId }).sort({ day: 1, startTime: 1 });
    res.json({ success: true, data: timeslots });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

/**
 * Get a single timeslot by ID
 */
export const getTimeslotById = async (req, res) => {
  try {
    const timeslot = await Timeslot.findById(req.params.id);
    if (!timeslot) return res.status(404).json({ success: false, message: "Timeslot not found" });
    res.json({ success: true, data: timeslot });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

/**
 * Update a timeslot
 */
export const updateTimeslot = async (req, res) => {
  try {
    const { id } = req.params;
    const update = req.body;

    const timeslot = await Timeslot.findByIdAndUpdate(id, update, { new: true });
    if (!timeslot) return res.status(404).json({ success: false, message: "Timeslot not found" });

    res.json({ success: true, data: timeslot });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

/**
 * Delete a timeslot
 */
export const deleteTimeslot = async (req, res) => {
  try {
    const { id } = req.params;
    const timeslot = await Timeslot.findByIdAndDelete(id);

    if (!timeslot) return res.status(404).json({ success: false, message: "Timeslot not found" });

    res.json({ success: true, message: "Timeslot deleted successfully" });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};
