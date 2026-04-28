import { type FormEvent, useState } from "react";

interface LoginFormProps {
  onSubmit: (username: string, password: string) => Promise<void>;
}

export function LoginForm({ onSubmit }: LoginFormProps) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsBusy(true);
    try {
      await onSubmit(username, password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={handleSubmit}>
        <p className="eyebrow">Internal V1</p>
        <h1>媒介知识与标注工作台</h1>
        <p className="muted-text">本地账号登录后可浏览数据库、执行人工审核、导出 reviewed episodes。</p>

        <label className="field-block">
          <span>用户名</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>

        <label className="field-block">
          <span>密码</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>

        {error ? <div className="error-banner">{error}</div> : null}

        <button className="primary-button" disabled={isBusy} type="submit">
          {isBusy ? "登录中..." : "登录"}
        </button>

        <div className="hint-card">
          <p className="muted-text">默认账号：</p>
          <p className="muted-text">admin / admin123</p>
          <p className="muted-text">annotator / annotator123</p>
          <p className="muted-text">viewer / viewer123</p>
        </div>
      </form>
    </div>
  );
}
