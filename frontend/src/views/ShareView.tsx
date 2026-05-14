import RankingPage from './RankingPage';
import LivePage from './LivePage';

export default function ShareView() {
  return (
    <div className="dark min-h-svh bg-background text-foreground">
      {/* Glow décoratif style ShopPulse */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden dark:block hidden z-0">
        <div className="absolute -top-[300px] -right-[200px] size-[700px] rounded-full bg-primary/[0.03] blur-[200px]" />
        <div className="absolute top-[40%] -left-[250px] size-[500px] rounded-full bg-accent-blue/[0.02] blur-[180px]" />
      </div>

      <div className="relative z-10 flex flex-col xl:flex-row gap-xl w-full max-w-[1800px] mx-auto p-md sm:p-xl lg:p-2xl h-screen">
        <div className="w-full xl:w-1/3 h-full overflow-y-auto custom-scrollbar rounded-2xl">
          <RankingPage />
        </div>
        <div className="w-full xl:w-2/3 h-full overflow-hidden rounded-2xl flex flex-col">
          <LivePage />
        </div>
      </div>
    </div>
  );
}
