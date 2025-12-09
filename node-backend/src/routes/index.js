
import organisationRoutes from "./organisation.routes.js";

import timetableRoutes from "./timetable.routes.js";
import verificationRoutes from "./verification.routes.js";
import passwordResetRoutes from "./passwordReset.routes.js";
import chatRoutes from "./chat.routes.js"
import uploadRoutes from "./upload.routes.js"
// import ragRoutes from "./rag.routes.js"
import contextRoutes from "./context.routes.js"
import senateRoutes from "./senate.routes.js";
import authorityRoutes from "./authority.routes.js"
import requestTimeTableRoutes from "./timetableRequest.routes.js"
import masterTimeTables from "./masterTimetable.routes.js"
import { Router } from "express";

const router = Router();

router.use("/organisation", organisationRoutes);
router.use("/timetable", timetableRoutes);
router.use("/verification", verificationRoutes);
router.use("/password-reset", passwordResetRoutes);
router.use("/chatbot",chatRoutes)
router.use("/document",uploadRoutes)
// router.use("/userRag",ragRoutes)
router.use("/context",contextRoutes)
router.use("/senate", senateRoutes);
router.use("/senates",authorityRoutes);
router.use("/request",requestTimeTableRoutes)
router.use("/super",masterTimeTables)
export default router;
