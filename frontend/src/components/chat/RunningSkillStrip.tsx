export function RunningSkillStrip({ skillName }: { skillName: string }) {
  return (
    <div className="running-skill-strip" aria-live="polite">
      <span className="running-dot" />
      <div>
        <strong>正在执行 {skillName}</strong>
        <p>读取已选资产、咨询知识库、调用模型并整理引用依据。</p>
      </div>
    </div>
  );
}

