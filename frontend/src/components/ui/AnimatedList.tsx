import { useRef, useEffect, useState, type ReactNode } from "react";
import { motion, useInView, useAnimation } from "framer-motion";

interface AnimatedListProps {
  items: ReactNode[];
  onItemSelect?: (item: ReactNode, index: number) => void;
  showGradients?: boolean;
  enableArrowNavigation?: boolean;
  displayScrollbar?: boolean;
  className?: string;
}

export default function AnimatedList({
  items,
  onItemSelect,
  showGradients = false,
  enableArrowNavigation = true,
  displayScrollbar = false,
  className = "",
}: AnimatedListProps) {
  const listRef = useRef<HTMLUListElement>(null);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const [keyboardNav, setKeyboardNav] = useState<boolean>(false);

  useEffect(() => {
    if (!enableArrowNavigation) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setKeyboardNav(true);
        setSelectedIndex((prev) => Math.min(prev + 1, items.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setKeyboardNav(true);
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter" && selectedIndex !== -1 && onItemSelect) {
        e.preventDefault();
        onItemSelect(items[selectedIndex], selectedIndex);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enableArrowNavigation, items, selectedIndex, onItemSelect]);

  useEffect(() => {
    if (keyboardNav && selectedIndex !== -1 && listRef.current) {
      const selectedElement = listRef.current.children[selectedIndex] as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      }
    }
  }, [selectedIndex, keyboardNav]);

  return (
    <div className={`relative w-full h-full overflow-hidden ${className}`}>
      {showGradients && (
        <>
          <div className="absolute top-0 left-0 right-0 h-12 bg-gradient-to-b from-background to-transparent z-10 pointer-events-none"></div>
          <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-background to-transparent z-10 pointer-events-none"></div>
        </>
      )}
      <ul
        ref={listRef}
        className={`w-full h-full flex flex-col gap-3 p-4 overflow-y-auto ${
          displayScrollbar ? "custom-scrollbar" : "scrollbar-hide"
        }`}
        style={{
          scrollbarWidth: displayScrollbar ? "auto" : "none",
          msOverflowStyle: displayScrollbar ? "auto" : "none",
        }}
      >
        {items.map((item, index) => {
          return (
            <AnimatedListItem
              key={index}
              index={index}
              isSelected={selectedIndex === index}
              onMouseEnter={() => {
                setKeyboardNav(false);
                setSelectedIndex(index);
              }}
              onClick={() => {
                if (onItemSelect) onItemSelect(item, index);
              }}
            >
              {item}
            </AnimatedListItem>
          );
        })}
      </ul>
    </div>
  );
}

interface AnimatedListItemProps {
  children: ReactNode;
  index: number;
  isSelected: boolean;
  onMouseEnter: () => void;
  onClick: () => void;
}

function AnimatedListItem({
  children,
  index,
  isSelected,
  onMouseEnter,
  onClick,
}: AnimatedListItemProps) {
  const ref = useRef<HTMLLIElement>(null);
  const isInView = useInView(ref as any, { once: true, margin: "-10% 0px" });
  const controls = useAnimation();

  useEffect(() => {
    if (isInView) {
      controls.start({ opacity: 1, y: 0 });
    }
  }, [isInView, controls]);

  return (
    <motion.li
      ref={ref as any}
      initial={{ opacity: 0, y: 20 }}
      animate={controls}
      transition={{
        duration: 0.4,
        delay: index * 0.1,
        ease: "easeOut",
      }}
      onMouseEnter={onMouseEnter}
      onClick={onClick}
      className={`cursor-pointer transition-all duration-300 rounded-xl outline-none ${
        isSelected
          ? "ring-2 ring-accent-blue bg-accent-blue/10 scale-[1.02]"
          : "hover:bg-white/5"
      }`}
    >
      {children}
    </motion.li>
  );
}
