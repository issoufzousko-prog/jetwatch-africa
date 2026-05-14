import { useState, useEffect } from "react";

interface TextTypeProps {
  text?: string | string[];
  texts?: string[];
  typingSpeed?: number;
  pauseDuration?: number;
  showCursor?: boolean;
  cursorCharacter?: string;
  deletingSpeed?: number;
  variableSpeedEnabled?: boolean;
  variableSpeedMin?: number;
  variableSpeedMax?: number;
  cursorBlinkDuration?: number;
  onComplete?: () => void;
  className?: string;
}

export default function TextType({
  text = "",
  texts = [],
  typingSpeed = 50,
  pauseDuration = 1500,
  showCursor = true,
  cursorCharacter = "_",
  deletingSpeed = 30,
  variableSpeedEnabled = false,
  variableSpeedMin = 30,
  variableSpeedMax = 80,
  cursorBlinkDuration = 0.5,
  onComplete,
  className = "",
}: TextTypeProps) {
  const [displayedText, setDisplayedText] = useState("");
  const [cursorVisible, setCursorVisible] = useState(true);
  
  // Combine text and texts props into a single array to process
  const items = Array.isArray(text) ? text : texts.length > 0 ? texts : [text];

  useEffect(() => {
    if (items.length === 0 || !items[0]) return;

    let timeoutId: number;
    let currentItemIndex = 0;
    let currentCharIndex = 0;
    let isDeleting = false;

    const typeCycle = () => {
      const currentFullText = items[currentItemIndex] || "";
      
      if (!isDeleting) {
        // Typing forward
        setDisplayedText(currentFullText.slice(0, currentCharIndex + 1));
        currentCharIndex++;

        if (currentCharIndex === currentFullText.length) {
          // Reached the end of the string
          if (currentItemIndex === items.length - 1 && items.length === 1) {
            // If it's a single static text, we stop here
            if (onComplete) onComplete();
            return;
          }
          isDeleting = true;
          timeoutId = window.setTimeout(typeCycle, pauseDuration);
        } else {
          // Keep typing
          let speed = typingSpeed;
          if (variableSpeedEnabled) {
            speed = Math.floor(Math.random() * (variableSpeedMax - variableSpeedMin + 1)) + variableSpeedMin;
          }
          timeoutId = window.setTimeout(typeCycle, speed);
        }
      } else {
        // Deleting backward
        setDisplayedText(currentFullText.slice(0, currentCharIndex - 1));
        currentCharIndex--;

        if (currentCharIndex === 0) {
          isDeleting = false;
          currentItemIndex = (currentItemIndex + 1) % items.length;
          timeoutId = window.setTimeout(typeCycle, typingSpeed);
        } else {
          timeoutId = window.setTimeout(typeCycle, deletingSpeed);
        }
      }
    };

    timeoutId = window.setTimeout(typeCycle, 100);

    return () => window.clearTimeout(timeoutId);
  }, [items, typingSpeed, pauseDuration, deletingSpeed, variableSpeedEnabled, variableSpeedMin, variableSpeedMax]);

  // Cursor blink effect
  useEffect(() => {
    if (!showCursor) return;
    const interval = setInterval(() => {
      setCursorVisible((v) => !v);
    }, cursorBlinkDuration * 1000);
    return () => clearInterval(interval);
  }, [showCursor, cursorBlinkDuration]);

  return (
    <span className={`inline-block ${className}`}>
      {displayedText}
      {showCursor && (
        <span 
          className="inline-block transition-opacity"
          style={{ opacity: cursorVisible ? 1 : 0 }}
        >
          {cursorCharacter}
        </span>
      )}
    </span>
  );
}
