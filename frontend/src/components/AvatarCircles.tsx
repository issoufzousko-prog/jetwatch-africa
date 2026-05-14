import React from "react";

interface Avatar {
  imageUrl: string;
  profileUrl: string;
}

interface AvatarCirclesProps {
  className?: string;
  numPeople?: number;
  avatarUrls: Avatar[];
}

export default function AvatarCircles({
  numPeople,
  className,
  avatarUrls,
}: AvatarCirclesProps) {
  return (
    <div className={`z-10 flex -space-x-4 rtl:space-x-reverse ${className || ""}`}>
      {avatarUrls.map((url, index) => (
        <a
          key={index}
          href={url.profileUrl || "#"}
          target={url.profileUrl ? "_blank" : "_self"}
          rel="noopener noreferrer"
          className="relative inline-block hover:z-20"
          onClick={(e) => {
            if (!url.profileUrl || url.profileUrl === "#") {
              e.preventDefault();
            }
          }}
        >
          <img
            className="h-10 w-10 rounded-full border-2 border-background bg-muted object-cover transition-transform duration-300 hover:scale-110"
            src={url.imageUrl || "https://ui-avatars.com/api/?name=User&background=random"}
            alt={`Avatar ${index + 1}`}
            referrerPolicy="no-referrer"
            onError={(e) => {
              (e.target as HTMLImageElement).src = "https://ui-avatars.com/api/?name=U&background=random";
            }}
          />
        </a>
      ))}
      {(numPeople ?? 0) > 0 && (
        <a
          className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-background bg-foreground text-center text-xs font-medium text-background hover:bg-muted-foreground transition-transform duration-300 hover:scale-110 z-10 hover:z-20"
          href="#"
          onClick={(e) => e.preventDefault()}
        >
          +{numPeople}
        </a>
      )}
    </div>
  );
}
