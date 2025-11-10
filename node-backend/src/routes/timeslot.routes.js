import { Router } from "express";
import { verifyJWT } from "../middlewares/auth.middleware.js";
import { createTimeslot, deleteTimeslot, getTimeslotById, updateTimeslot } from "../controllers/timeslot.controllers.js";
import {getTimeslotsByOrganisation}  from "../controllers/timeslot.controllers.js"


const router = Router();


router.use(verifyJWT);


router.post("/create",createTimeslot);
router.get("/getTimeslotsByOrganisation",getTimeslotsByOrganisation)
router.delete("/delete",deleteTimeslot);
router.put("/update",updateTimeslot);
router.get("/getTimesSlot/:id",getTimeslotById);




export default router;
