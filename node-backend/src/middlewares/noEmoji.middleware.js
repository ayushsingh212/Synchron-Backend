
const emojiRegex = /\p{Extended_Pictographic}/u;


function containsEmoji(data) {
  if (!data) return false;

  if (typeof data === "string") {
    return emojiRegex.test(data);
  }

  if (Array.isArray(data)) {
    return data.some((item) => containsEmoji(item));
  }

  if (typeof data === "object") {
    return Object.values(data).some((value) => containsEmoji(value));
  }

  return false;
}

export const noEmojiMiddleware = (req, res, next) => {
  try {
    if (
      containsEmoji(req.body) ||
      containsEmoji(req.params) ||
      containsEmoji(req.query)
    ) {
      return res.status(400).json({
        success: false,
        message: "Emoji characters are not allowed in input fields",
      });
    }

    next();
  } catch (error) {
    console.error("Emoji validation error:", error);
    return res.status(500).json({
      success: false,
      message: "Internal error validating emoji",
    });
  }
};
