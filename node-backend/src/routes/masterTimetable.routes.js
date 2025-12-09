import { Router } from "express";
import { verifyJWT } from "../middlewares/auth.middleware.js";
import { getOrganisationMasterTimetable } from "../controllers/mastertimetable.controller.js";



const router = Router();

router.get("/master/full", verifyJWT,getOrganisationMasterTimetable);



export default router;