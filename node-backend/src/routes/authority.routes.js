import { Router } from "express";
import { createSenate, listSenates, removeSenate } from "../controllers/authority.controller.js";
import { verifyJWT } from "../middlewares/auth.middleware.js";
import { verifyAdminToken } from "../middlewares/admin.middleware.js";



const router = Router();

router.use(verifyJWT,verifyAdminToken);

router.post("/addSenate",createSenate);
router.delete("/removeSenate/:senateId",removeSenate );
router.get("/listSenates",listSenates ); 


export default router;