import React from "react";
import {
  AbsoluteFill,
  Easing,
  Html5Video,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { DISPLAY, FontFaces, INTER, MONO } from "./GstBrand";

export type ToweringRigProps = {
  media: string;
  mediaKind: "video" | "image";
  headline: string;
  specLine1: string;
  specLine2: string;
  specLine3: string;
  price: string;
  sellerName: string;
  sellerLogo: string;
  phone: string;
  email: string;
  website: string;
  accent: string;
  accentDark: string;
};

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

const Beat: React.FC<{
  start: number;
  end: number;
  children: React.ReactNode;
  align?: "left" | "center";
}> = ({ start, end, children, align = "left" }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [start, start + 14, Math.max(start + 15, end - 12), end],
    [0, 1, 1, 0],
    clamp,
  );
  const y = interpolate(frame, [start, start + 18], [34, 0], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });

  return (
    <div
      style={{
        position: "absolute",
        left: 72,
        right: 72,
        top: 1090,
        textAlign: align,
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      {children}
    </div>
  );
};

export const ToweringRig: React.FC<ToweringRigProps> = ({
  media,
  mediaKind,
  headline,
  specLine1,
  specLine2,
  specLine3,
  price,
  sellerName,
  sellerLogo,
  phone,
  email,
  website,
  accent,
  accentDark,
}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 449], [1, 1.055], {
    ...clamp,
    easing: Easing.inOut(Easing.quad),
  });
  const drift = interpolate(frame, [0, 449], [0, -22], clamp);
  const mediaOpacity = interpolate(frame, [390, 410], [1, 0.34], clamp);
  const endOpacity = interpolate(frame, [390, 408], [0, 1], clamp);
  const endY = interpolate(frame, [390, 414], [34, 0], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });

  const mediaStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "contain",
    transform: `translateY(${drift}px) scale(${scale})`,
    opacity: mediaOpacity,
  };

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(180deg,#0b0f0d,#111614)",
        color: "#fff",
      }}
    >
      <FontFaces />
      <AbsoluteFill style={{ overflow: "hidden" }}>
        {mediaKind === "video" ? (
          <Html5Video src={staticFile(media)} muted style={mediaStyle} />
        ) : (
          <Img src={staticFile(media)} style={mediaStyle} />
        )}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg,rgba(8,12,10,.72) 0%,rgba(8,12,10,0) 28%,rgba(8,12,10,.18) 54%,rgba(8,12,10,.94) 82%,#0b0f0d 100%)",
        }}
      />

      <div
        style={{
          position: "absolute",
          top: 178,
          left: 72,
          right: 72,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div
          style={{
            fontFamily: MONO,
            fontSize: 26,
            letterSpacing: "0.14em",
          }}
        >
          <span style={{ color: accent }}>●</span> GST CRANES
        </div>
        <div
          style={{
            backgroundColor: accent,
            borderRadius: 999,
            padding: "12px 22px",
            fontFamily: MONO,
            fontSize: 24,
            letterSpacing: "0.1em",
          }}
        >
          FOR SALE
        </div>
      </div>

      <Beat start={0} end={60}>
        <div
          style={{
            fontFamily: DISPLAY,
            fontWeight: 800,
            fontSize: 76,
            lineHeight: 0.98,
            letterSpacing: "-0.025em",
          }}
        >
          {headline}
        </div>
        <div
          style={{
            width: 210,
            height: 8,
            borderRadius: 8,
            backgroundColor: accent,
            marginTop: 28,
          }}
        />
      </Beat>

      {[
        { start: 60, end: 150, text: specLine1 },
        { start: 150, end: 240, text: specLine2 },
        { start: 240, end: 300, text: specLine3 },
      ].map((beat) => (
        <Beat key={beat.start} start={beat.start} end={beat.end}>
          <div
            style={{
              fontFamily: MONO,
              color: accent,
              fontSize: 24,
              letterSpacing: "0.14em",
              marginBottom: 18,
            }}
          >
            VERIFIED SPECIFICATION
          </div>
          <div
            style={{
              fontFamily: DISPLAY,
              fontWeight: 800,
              fontSize: 68,
              lineHeight: 1.04,
            }}
          >
            {beat.text}
          </div>
        </Beat>
      ))}

      <Beat start={300} end={390} align="center">
        <div
          style={{
            display: "inline-block",
            background: `linear-gradient(135deg,${accentDark},${accent})`,
            borderRadius: 24,
            padding: "34px 52px 38px",
            boxShadow: "0 24px 80px rgba(0,0,0,.36)",
          }}
        >
          <div
            style={{
              fontFamily: MONO,
              fontSize: 24,
              letterSpacing: "0.16em",
            }}
          >
            ASKING PRICE
          </div>
          <div
            style={{
              fontFamily: DISPLAY,
              fontWeight: 800,
              fontSize: 96,
              letterSpacing: "-0.035em",
              marginTop: 8,
            }}
          >
            {price}
          </div>
        </div>
      </Beat>

      <div
        style={{
          position: "absolute",
          left: 72,
          right: 72,
          top: 910,
          opacity: endOpacity,
          transform: `translateY(${endY}px)`,
        }}
      >
        <div
          style={{
            background: "rgba(255,255,255,.97)",
            color: "#0f1511",
            borderRadius: 28,
            padding: "38px 42px",
            boxShadow: "0 24px 90px rgba(0,0,0,.4)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
            <Img
              src={staticFile(sellerLogo)}
              style={{
                width: 112,
                height: 112,
                objectFit: "contain",
                borderRadius: 16,
              }}
            />
            <div>
              <div
                style={{
                  fontFamily: DISPLAY,
                  fontWeight: 800,
                  fontSize: 66,
                }}
              >
                {sellerName}
              </div>
              <div
                style={{
                  fontFamily: MONO,
                  color: accentDark,
                  fontSize: 22,
                  letterSpacing: "0.1em",
                }}
              >
                DIRECT SELLER
              </div>
            </div>
          </div>
          <div
            style={{
              height: 1,
              backgroundColor: "#dce5df",
              margin: "28px 0",
            }}
          />
          <div
            style={{
              fontFamily: INTER,
              fontWeight: 700,
              fontSize: 34,
              lineHeight: 1.55,
            }}
          >
            {phone}
          </div>
          <div
            style={{
              fontFamily: INTER,
              fontWeight: 700,
              fontSize: 34,
              lineHeight: 1.55,
            }}
          >
            {email}
          </div>
          <div
            style={{
              marginTop: 24,
              backgroundColor: accent,
              color: "#fff",
              borderRadius: 12,
              padding: "18px 22px",
              fontFamily: MONO,
              fontSize: 28,
              textAlign: "center",
              letterSpacing: "0.05em",
            }}
          >
            FULL LISTING · {website}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
