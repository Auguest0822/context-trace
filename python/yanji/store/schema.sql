-- memories: 一条记忆 = 一条可检索、可追溯、可失效的记录
CREATE TABLE memories (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  scope         VARCHAR(128) NOT NULL,   -- 归属：项目/团队/个人
  kind          VARCHAR(32)  NOT NULL,   -- decision / constraint / fact / preference / skill
  content       TEXT         NOT NULL,
  summary       VARCHAR(512),            -- 压缩后摘要
  embedding     VECTOR(1024),
  importance    FLOAT        DEFAULT 0.5,
  status        VARCHAR(16)  DEFAULT 'active',  -- active / superseded / expired
  superseded_by BIGINT,                  -- 被哪条新记忆取代（版本链）
  source_type   VARCHAR(32),             -- chat / doc / git / issue / manual
  source_ref    VARCHAR(512),            -- 出处：会话ID+时间戳 / 文件+页码 / commit
  valid_from    DATETIME,
  valid_to      DATETIME,
  created_at    DATETIME,
  updated_at    DATETIME,
  FULLTEXT INDEX idx_ft (content) WITH PARSER ik,
  VECTOR INDEX idx_vec (embedding) WITH (DISTANCE=l2, TYPE=hnsw)
) ORGANIZATION = HEAP;
