import jwt from "jsonwebtoken";
import ApiError from "../utils/apiError.js";

export const verifySenateToken = (req, res, next) => {
  const token = req.cookies.senateToken || req.cookies.adminToken || req.headers.authorization?.split(" ")[1];
  if (!token) throw new ApiError(401, "Token required");

  let decoded;

  try {
    decoded = jwt.verify(token, process.env.SENATE_TOKEN_SECRET);
    if (decoded.type !== "SENATE") throw new Error();
    req.senate = decoded;
    return next();
  } catch {}

  try {
    decoded = jwt.verify(token, process.env.ADMIN_TOKEN_SECRET);
    if (decoded.type !== "ADMIN") throw new Error();
    req.admin = decoded;
    return next();
  } catch {}

  throw new ApiError(401, "Invalid token");
};
