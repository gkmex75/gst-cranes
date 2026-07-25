import React from "react";
import { Composition, staticFile } from "remotion";
import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { CraneExplainer } from "./CraneExplainer";
import { crane } from "./data";
import { PlatformPromo } from "./PlatformPromo";
import { promo } from "./platformData";
import { IronGiant } from "./IronGiant";
import { IronFrame } from "./IronFrame";
import { IronReveal } from "./IronReveal";
import { FleetDrop } from "./FleetDrop";
import { CarouselSlide } from "./CarouselSlide";
import { BrokerMath } from "./BrokerMath";
import { DemoWrap } from "./DemoWrap";
import { SearchBurst } from "./SearchBurst";
import { CommunityPulse } from "./CommunityPulse";
import { Anthem } from "./Anthem";
import { WantedRadar } from "./WantedRadar";
import { StorySlogan } from "./StorySlogan";
import { ToweringRig } from "./ToweringRig";

export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="CraneExplainer"
      component={CraneExplainer}
      durationInFrames={crane.durationInFrames}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={crane}
      calculateMetadata={async ({ props }) => {
        try {
          const seconds = await getAudioDurationInSeconds(staticFile(props.audio));
          return { durationInFrames: Math.ceil((seconds + 0.6) * 30) };
        } catch (e) {
          return { durationInFrames: props.durationInFrames };
        }
      }}
    />
    <Composition
      id="StorySlogan"
      component={StorySlogan}
      durationInFrames={240}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{ tag: "AI SEARCH", l1: "One line in.", l2: "The whole market out.", sub: "", dark: false, move: "slide" }}
    />
    {[
      { id: "CommunityPulse", component: CommunityPulse, props: { audio: "narration_community.mp3", endLine1: "THE AI CRANE MARKETPLACE", endLine2: "FIRST 500 MEMBERS · 100 FREE CREDITS" } },
      { id: "Anthem", component: Anthem, props: { audio: "narration_anthem.mp3", endLine1: "NO OTHER CRANE SITE DOES THIS", endLine2: "FIRST 500 MEMBERS · 100 FREE CREDITS" } },
      { id: "WantedRadar", component: WantedRadar, props: { audio: "narration_radar.mp3", query: "LTM 1230-5", endLine1: "POST WHAT YOU NEED · ONCE", endLine2: "FIRST 500 MEMBERS · 100 FREE CREDITS" } },
    ].map((c) => (
      <Composition
        key={c.id}
        id={c.id}
        component={c.component as any}
        durationInFrames={900}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={c.props}
        calculateMetadata={async ({ props }) => {
          try {
            const seconds = await getAudioDurationInSeconds(staticFile((props as any).audio));
            return { durationInFrames: Math.ceil((seconds + 0.6) * 30) };
          } catch (e) {
            return { durationInFrames: 900 };
          }
        }}
      />
    ))}
    <Composition
      id="SearchBurst"
      component={SearchBurst}
      durationInFrames={900}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{ audio: "narration_searchburst.mp3", query: "", cards: [], statLine: "", endLine1: "", endLine2: "" }}
      calculateMetadata={async ({ props }) => {
        try {
          const seconds = await getAudioDurationInSeconds(staticFile(props.audio));
          return { durationInFrames: Math.ceil((seconds + 0.6) * 30) };
        } catch (e) {
          return { durationInFrames: 900 };
        }
      }}
    />
    <Composition
      id="PlatformPromo"
      component={PlatformPromo}
      durationInFrames={promo.durationInFrames}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={promo}
      calculateMetadata={async ({ props }) => {
        try {
          const seconds = await getAudioDurationInSeconds(staticFile(props.audio));
          return { durationInFrames: Math.ceil((seconds + 0.6) * 30) };
        } catch (e) {
          return { durationInFrames: props.durationInFrames };
        }
      }}
    />
    <Composition
      id="IronGiant"
      component={IronGiant}
      durationInFrames={392}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        clip: "w_11200.mp4",
        loopFrames: 151,
        seller: { logo: "seller_gkmex.png", name: "Gkmex", sub: "VERIFIED LISTING · GSTCRANES.COM" },
        lines: {
          machine: "Liebherr LTM 11200-9.1",
          detail: "1,200 t · 2010 · €2,350,000 · 0% commission",
          cta: "CONTACT GKMEX DIRECT ON THE LISTING →",
        },
        endLine1: "SEARCH THE WHOLE CRANE MARKET",
        endLine2: "FREE ACCOUNT · 50 CREDITS",
      }}
    />
    <Composition
      id="IronFrame"
      component={IronFrame}
      durationInFrames={392}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        clip: "w_1300.mp4",
        loopFrames: 150,
        seller: { logo: "seller_gkmex.png", name: "Gkmex", sub: "VERIFIED LISTING · GSTCRANES.COM" },
        lines: {
          machine: "Liebherr LTM 1300-6.2",
          detail: "300 t · 2015 · €795,000 · 0% commission",
          cta: "info@gkmex.com · +90 545 686 7277",
        },
        endLine1: "SEARCH THE WHOLE CRANE MARKET",
        endLine2: "FIRST 500 MEMBERS · 100 FREE CREDITS",
      }}
    />
    <Composition
      id="IronReveal"
      component={IronReveal}
      durationInFrames={392}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        clip: "w_11200.mp4",
        loopFrames: 150,
        seller: { logo: "seller_gkmex.png", name: "Gkmex" },
        machine: "Liebherr LTM 11200-9.1",
        specs: [
          { k: "CAPACITY", v: "1,200 t" },
          { k: "YEAR", v: "2010" },
          { k: "AXLES", v: "9" },
          { k: "PRICE", v: "€2,350,000" },
        ],
        cta: "info@gkmex.com · +90 545 686 7277",
        endLine1: "SEARCH THE WHOLE CRANE MARKET",
        endLine2: "FIRST 500 MEMBERS · 100 FREE CREDITS",
      }}
    />
    <Composition
      id="FleetDrop"
      component={FleetDrop}
      durationInFrames={420}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        per: 110,
        machines: [
          { clip: "w_1750.mp4", loopFrames: 150, name: "Liebherr LTM 1750-9.1", price: "€4,900,000", sub: "800 t · 2022 · 380 h", tag: "FLAGSHIP" },
          { clip: "w_11200.mp4", loopFrames: 150, name: "Liebherr LTM 11200-9.1", price: "€2,350,000", sub: "1,200 t · 2010", tag: "FOR SALE" },
          { clip: "w_cc2800.mp4", loopFrames: 150, name: "Demag CC 2800-1", price: "€1,450,000", sub: "600 t · 2006", tag: "CRAWLER" },
        ],
        endLine1: "THREE MACHINES · ONE MEMBER",
        endLine2: "0% COMMISSION · GSTCRANES.COM",
      }}
    />
    <Composition
      id="CarouselSlide"
      component={CarouselSlide}
      durationInFrames={30}
      fps={30}
      width={1080}
      height={1350}
      defaultProps={{
        kind: "hero",
        machine: "Liebherr LTM 1750-9.1",
        photo: "car_hero.png",
        seller: { logo: "seller_gkmex.png", name: "Gkmex" },
        specs: [],
        valueLines: [],
      }}
    />
    <Composition
      id="BrokerMath"
      component={BrokerMath}
      durationInFrames={540}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{ audio: "narration_brokermath.mp3" }}
      calculateMetadata={async ({ props }) => {
        try {
          const seconds = await getAudioDurationInSeconds(staticFile(props.audio));
          return { durationInFrames: Math.max(540, Math.ceil((seconds + 0.6) * 30)) };
        } catch (e) {
          return { durationInFrames: 540 };
        }
      }}
    />
    <Composition
      id="DemoOneSentence"
      component={DemoWrap}
      durationInFrames={66 + 868 + 120}
      calculateMetadata={async ({ props }) => ({
        durationInFrames: 66 + (props.demoDurationInFrames ?? 868) + 150,
      })}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        demo: "demo_onesentence.mp4",
        demoDurationInFrames: 868,
        audio: "narration_demo1.mp3",
        kicker: "AI SEARCH · LIVE DEMO",
        title: "One sentence.\nThe whole market.",
        subtitle: "TYPED LIVE · REAL RESULTS",
        urlBar: "gstcranes.com/marketplace",
        endLine1: "SEARCH THE WHOLE CRANE MARKET",
        endLine2: "1 CREDIT PER SEARCH · 50 FREE ON SIGN-UP",
      }}
    />
    <Composition
      id="ToweringRig"
      component={ToweringRig}
      durationInFrames={450}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        media: "gkmex-cc2400-11200h-original.jpg",
        mediaKind: "image",
        headline: "TEREX DEMAG CC 2400-1",
        specLine1: "2007 · 400 T · 11,200 HOURS",
        specLine2: "84 M BOOM · 84 M LUFFING JIB",
        specLine3: "12 M FIXED JIB · 30 M SUPERLIFT MAST",
        price: "€1,250,000",
        sellerName: "Gkmex",
        sellerLogo: "seller_gkmex.png",
        phone: "+90 545 686 72 77",
        email: "gkm@gkmex.com",
        website: "gstcranes.com",
        accent: "#16A34A",
        accentDark: "#15803D",
      }}
    />
    </>
  );
};
