import { Router } from "express";
import { createSenate, listSenates, removeSenate } from "../controllers/authority.controller";
import { verifyJWT } from "../middlewares/auth.middleware";
import { verifyAdminToken } from "../middlewares/admin.middleware";



const router = Router();

router.use(verifyJWT,verifyAdminToken);

router.post("/addSenate",createSenate);
router.delete("/removeSenate/:senateId",removeSenate );
router.get("/listSenates",listSenates ); 