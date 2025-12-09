import { Router } from "express";
import {
  createTimetableRequest,
  listTimetableRequests,
  approveTimetableRequest,
  rejectTimetableRequest,
  deleteTimetableRequest
} from "../controllers/timetableRequest.controllers.js     ";

import { verifySenateToken } from "../middlewares/senate.middleware.js";
import { verifyAdminToken } from "../middlewares/admin.middleware.js";
import { verifyJWT } from "../middlewares/auth.middleware.js";

const router = Router();


router.post("/send", verifyJWT, verifySenateToken, createTimetableRequest);

// Admin views all requests
router.get("/all", verifyJWT, verifyAdminToken, listTimetableRequests);

// Admin approves
router.put("/approve/:requestId", verifyJWT, verifyAdminToken, approveTimetableRequest);

// Admin rejects
router.put("/reject/:requestId", verifyJWT, verifyAdminToken, rejectTimetableRequest);

// Optional delete
router.delete("/delete/:requestId", verifyJWT, verifyAdminToken, deleteTimetableRequest);

export default router;
