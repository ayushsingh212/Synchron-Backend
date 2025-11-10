import { Room } from "../models/room.model.js";
import asyncHandler from "../utils/asyncHandler.js";

/**
 * Create a new room
 */
export const createRoom =  asyncHandler( async (req, res) => {
  
  console.log("I am working bro");
   const organisationId = req.organisation?._id;

    const {  name, capacity, type } = req.body;
   
 console.log("I have pased",organisationId);


    if (!organisationId || !name) {
      return res.status(400).json({ success: false, message: "organisationId and name are required" });
    }

    const room = new Room({ organisationId, name, capacity, type });
    await room.save();

    res.status(201).json({ success: true, data: room });
  
});

/**
 * Get all rooms for an organisation
 */
export const getRoomsByOrganisation = async (req, res) => {
  try {
    const { organisationId } = req.params;
    const rooms = await Room.find({ organisationId });
    res.json({ success: true, data: rooms });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

/**
 * Get a single room by ID
 */
export const getRoomById = async (req, res) => {
  try {
    const room = await Room.findById(req.params.id);
    if (!room) return res.status(404).json({ success: false, message: "Room not found" });
    res.json({ success: true, data: room });
  } catch (err) {

  
    res.status(500).json({ success: false, message: err.message });
  }
};

/**
 * Update room details
 */
export const updateRoom = async (req, res) => {
  try {
    const { id } = req.params;
    const update = req.body;

    const room = await Room.findByIdAndUpdate(id, update, { new: true });
    if (!room) return res.status(404).json({ success: false, message: "Room not found" });

    res.json({ success: true, data: room });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

/**
 * Delete a room
 */
export const deleteRoom = async (req, res) => {
  try {
    const { id } = req.params;
    const room = await Room.findByIdAndDelete(id);

    if (!room) return res.status(404).json({ success: false, message: "Room not found" });

    res.json({ success: true, message: "Room deleted successfully" });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};
