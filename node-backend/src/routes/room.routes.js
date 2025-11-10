import { Router } from "express";
import { verifyJWT } from "../middlewares/auth.middleware.js";
import { createRoom, deleteRoom, getRoomById, getRoomsByOrganisation, updateRoom } from "../controllers/room.controllers.js";


const router = Router();



router.use(verifyJWT);

router.post("/createRoom",createRoom);
router.get("/getRooms/:organisationId",getRoomsByOrganisation)
router.get("/getRoomById",getRoomById);
router.put("/update",updateRoom);
router.delete("/delete/:id",deleteRoom);


export default router;