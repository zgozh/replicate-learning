# 六节九子块样例（ragent 批次3 节选）—— ⑥ "先讲一些东西 → 代码 → 再讲一堆东西" 实物参照

> **来源**：`D:/ragent-official/NOTES/教学讲解/第一册-项目源码与工程实现/阶段1-启动装配与配置契约/批次3-统一响应与异常族（Result★+AbstractException★+ClientException+RemoteException+ServiceException）.md`（2026-09-18 用户钦定的结构基准；闸门 ⓪c 双零分：0/39 缺白话开场、0/5 缺构造手法；`scan_detail.py` 0 缺口）。
> **本文件是什么**：⑥ 逐件讲解**九个子块**的整件实物（6.1 Result★，91 行）+ ②③④⑤ 四节的排版实物（原样节选，未改一字）。写 ⑥ 时**逐块对照**：★ 件十块全开；非★ 件去掉【讲解】与【怎么接】。
> **形态横幅**（照抄 vs 不能抄）：
> - 可照抄：子块顺序与命名标记（`**白话开场**：`/`**构造方式与手法**：`/`**逐行要点表**：`/`**边界与副作用**：`/`【讲解】`/`【怎么用】`/`【上下游】`/`【怎么接】`）、逐行要点表的聚合行段写法、上下游四列表、怎么接五段式。
> - 不能抄：Java 代码与行号、该批的业务事实、`// :Lnn` 行号（必须由 `inject_source.py` 注入）；本文是**节选**，不能当全批达标线（血证 H10）。

## ② 业务场景与端到端闭环

**一句话场景开场**：用户在控制台点"发送"，后端某处校验失败（例如"会话标题不能为空"），前端最终收到 `{"code":"A000001","message":"用户端错误"}` 这样的 JSON——本批要闭环的正是"**从 throw 到 JSON**"这一段。

完整闭环：

```text
前端请求 POST /api/ragent/agent/conversation
   │ HTTP + JSON body
   ▼
Controller                     ← 只做参数接收与调用（成功时 return Results.success(data)）
   │ 调用
   ▼
Service / 业务组件              ← 真正的校验与业务规则
   │ 校验不通过：throw new ClientException("会话标题不能为空")
   ▼
ClientException 构造器          ← 4 个构造器，挑最省事的一个
   │ this(message, null, BaseErrorCode.CLIENT_ERROR)
   ▼
AbstractException 构造器        ← 把 IErrorCode 译成两个字符串（errorCode / errorMessage）
   │ super(message, throwable) + 回退到 errorCode.message()
   ▼
Spring MVC 异常派发             ← 找最匹配的 @ExceptionHandler
   │ @ExceptionHandler(AbstractException.class)
   ▼
GlobalExceptionHandler          ← 记日志 + 决定给前端看什么
   │ Results.failure(ex)
   ▼
Result 信封（code/message/data）
   │ JSON 序列化
   ▼
前端按 code 分流               ← code == "0" 成功；A* 提示用户改输入；B* 提示重试；C* 提示第三方不可用
```

**分支流预告**（4 条分支，本批的"故事"就在分支上）：

- **正常流**：`Controller` 直接 `return Results.success(data)`（真实调用点 `agent/.../AgentConversationController.java:50`）。
- **业务异常分支**：任何 `AbstractException` 子类 → `GlobalExceptionHandler.java:92` 的 `abstractException` 处理器；响应码**仍是 HTTP 200**，失败写在 body 的 `code` 里。
- **参数校验分支**：`MethodArgumentNotValidException`（`GlobalExceptionHandler.java:61`）与 `HandlerMethodValidationException`（`:76`）→ 校验消息单独包装（与业务异常分开，便于前端做表单提示）。
- **认证/上传/兜底分支**：`NotLoginException`（`:111`）、`NotRoleException`（`:120`）、`MaxUploadSizeExceededException`（`:129`）、`Throwable`（`:145`）——最后一条是"谁都没接住"的兜底，**它决定用户看到的是"系统开小差"还是空白页**。

---

## ③ 文件清单与一句话职责

**源文件 5 个（本批主讲）**

| # | 文件 | 行数 | 一句话职责 | ★ |
|---|---|---|---|---|
| 1 | `framework/src/main/java/com/nageoffer/ai/ragent/framework/convention/Result.java` | 91 | 统一响应信封：`code`/`message`/`data`/`requestId` + 成功判定 | ★ |
| 2 | `framework/src/main/java/com/nageoffer/ai/ragent/framework/exception/AbstractException.java` | 41 | 异常族基类：把 `IErrorCode` 译成 `errorCode`/`errorMessage` 两个**不可变**字符串 | ★ |
| 3 | `framework/src/main/java/com/nageoffer/ai/ragent/framework/exception/ClientException.java` | 52 | A 段失败（用户端/参数）：4 个构造器 + 定制的 `toString()` | |
| 4 | `framework/src/main/java/com/nageoffer/ai/ragent/framework/exception/RemoteException.java` | 48 | C 段失败（第三方调用）：3 个构造器 + 定制的 `toString()` | |
| 5 | `framework/src/main/java/com/nageoffer/ai/ragent/framework/exception/ServiceException.java` | 55 | B 段失败（服务端执行）：4 个构造器 + `Optional` 兜住 null message | |

**本批必须一起读的关联件 4 个（不在本批 5 件内，但缺了它们讲不通）**

| 文件（行数） | 它在链路里的位置 | 不读它会漏什么 |
|---|---|---|
| `framework/.../errorcode/IErrorCode.java`（35） | 错误码接口：`code()`:29 / `message()`:34 | 不知道 `errorCode.code()` 从哪来，异常族的"译"就讲不清 |
| `framework/.../errorcode/BaseErrorCode.java`（152） | 错误码枚举：A/B/C 三段前缀（`:40`/`:108`/`:120`） | 讲不出"为什么分三段"，也看不出错误码是**契约**而非文案 |
| `framework/.../web/GlobalExceptionHandler.java`（157） | 异常的**唯一消费方**：7 个 `@ExceptionHandler` | 闭环断在"抛完之后"，读者不知道谁把异常变成 JSON |
| `framework/.../web/Results.java`（78） | 信封的静态工厂：`success()`:34、`failure()`:51、`failure(AbstractException)`:60 | 讲不出"为什么禁止手搓 `new Result<>()`" |

**测试文件：本批 5 件没有直接单测**（诚实声明）——framework 模块的 22 例分布在下列 5 个类里，它们**都不覆盖本批 5 件**：

| # | 文件 | 例数 | 测什么（关键断言） |
|---|---|---|---|
| 1 | `framework/src/test/java/com/nageoffer/ai/ragent/framework/web/StreamTaskManagerTest.java` | 10 | 流式任务注册/取消/超时清理 |
| 2 | `framework/src/test/java/com/nageoffer/ai/ragent/framework/convention/RetrievedChunkKeyTest.java` | 4 | 召回结果键的构造与去重约定 |
| 3 | `framework/src/test/java/com/nageoffer/ai/ragent/framework/mq/producer/RocketMQProducerAdapterTest.java` | 4 | MQ 生产者失败/超时降级 |
| 4 | `framework/src/test/java/com/nageoffer/ai/ragent/framework/validation/ChatQuestionTest.java` | 3 | 提问参数校验 |
| 5 | `framework/src/test/java/com/nageoffer/ai/ragent/framework/idempotent/IdempotentSubmitAspectTest.java` | 1 | 幂等切面第二次提交被拒 |

> **注意**：`RetrievedChunkKeyTest` 的包名里带 `convention`，与 `Result` 同包**但不同类**——它测的是召回结果键，不是响应信封。**"同包"不等于"覆盖"**，这是读测试表最容易踩的误判（⑪ 会再钉一次）。

---

## ④ 新概念白话解释

| 概念 | 一句话白话 | 本批在哪出现 |
|---|---|---|
| 统一响应信封 | 所有接口无论成败都返回同一个外层结构，前端只认这一个形状 | `Result.java:38`（类声明）、`:49`（成功码） |
| 业务码 vs HTTP 码 | HTTP 200 表示"服务器处理完了"，body 里的 `code` 表示"业务上成没成" | `Result.java:57` 的 `code` 是 `String`，不是 HTTP 状态 |
| 错误码契约 | `A000001` 这种码是**对外承诺**，改它等于改接口 | `BaseErrorCode.java:40`/`:108`/`:120` 三段前缀 |
| 异常族基类 | 三种失败共享的父类，负责"把错误码 + 消息装配好" | `AbstractException.java:30-40` |
| 责任方分段 | A=用户端、B=服务端、C=第三方：同一句"失败"，责任方不同处理方式不同 | `ClientException`/`ServiceException`/`RemoteException` |
| 不可变字段 | `errorCode`/`errorMessage` 是 `public final`，构造后不能改 | `AbstractException.java:32-34` |
| 消息回退 | 调用方没给 message 时，用错误码自带的默认文案 | `AbstractException.java:39`、`ServiceException.java:45` |
| 链式 setter | `new Result<>().setCode(...).setData(...)` 一行装配 | `Result.java:37`（`@Accessors(chain = true)`） |
| 序列化契约 | 信封要跨进程/缓存传递，必须可序列化并带版本号 | `Result.java:38`（`implements Serializable`）、`:41`（`serialVersionUID`） |
| 兜底处理器 | 没人接住的异常也会被转成信封，而不是抛给容器 | `GlobalExceptionHandler.java:145-146`（`@ExceptionHandler(Throwable.class)`） |
| 请求追踪号 | 每个响应带一个 `requestId`，让"用户截图"能对应到"服务端日志" | `Result.java:81`、`GlobalExceptionHandler` 的日志行（`:95`/`:104`） |

#### 4.1 `统一响应信封`（本批 2 个核心概念之一）

**是什么**：一个**只有 4 个字段**的外层对象——`code`（业务码）、`message`（给人看的话）、`data`（成功时的载荷）、`requestId`（追踪号）。对比两种做法：

| 做法 | 成功时 | 失败时 | 前端要写的分支 |
|---|---|---|---|
| 裸 DTO + HTTP 状态码 | 200 + 业务对象 | 400/500 + 框架默认错误体（结构不由你定） | 先判 `status`，再猜 body 结构 |
| **统一信封（本仓做法）** | 200 + `{code:"0", data:{...}}` | **200** + `{code:"A000001", message:"…"}` | 只看 `code`（`Result.isSuccess()` :88） |

**解决什么问题**：前端只需要一处判断。真实证据：工厂方法 `Results.success()`（`Results.java:34`）与失败路径 `Results.failure(AbstractException)`（`:60`）产出的是**同一个类**的实例，前端不会遇到"两种形状"。

**不用它会怎样**：每个 Controller 自己拼 `Map`/自定义 VO，字段名与语义漂移——`{"ok":true}`、`{"success":1}`、`{"errCode":...}` 混在一起，前端必须逐接口适配；更糟的是**失败时没有稳定字段**，日志里只有 HTTP 500，无法按错误码做统计与告警。

**本批的具体用法**：

```java
// 成功：用工厂，不要手搓（工厂保证 code 一定被设成 "0"）
return Results.success(orderVO);            // Results.java:42

// 失败：抛异常，让 GlobalExceptionHandler 统一翻译（不要在 Controller 里拼失败信封）
if (!StringUtils.hasText(title)) {
    throw new ClientException("会话标题不能为空");   // ClientException.java:33 → A000001
}
```

**代价**：① 失败响应与 HTTP 语义脱钩——**HTTP 200 承载业务失败**，对"只看状态码"的监控/网关不友好（需要额外约定）；② 信封多一层包装，前端取值路径变长；③ `data` 是泛型 `T`，反序列化时需要 `TypeReference` 才能还原具体类型。

#### 4.2 `异常族三层与错误码传递`（本批 2 个核心概念之二）

**是什么**：一棵三层树——`RuntimeException` → `AbstractException`（共享字段与翻译逻辑）→ 三个语义子类（A/B/C）。三层各管一件事：

| 层 | 管什么 | 本批证据 |
|---|---|---|
| `RuntimeException` | 让异常**不被强制 catch**（业务校验失败不需要调用方 try） | `AbstractException.java:30` |
| `AbstractException` | 把 `IErrorCode` **翻译**成 `errorCode` + `errorMessage` 两个字符串；保证 `cause` 可传 | `:36-40` |
| 三个子类 | 用**默认错误码**把"一次 throw"缩短到一行，并给 `toString()` 定制输出 | `ClientException.java:33`、`ServiceException.java:32`、`RemoteException.java:29` |

**解决什么问题**：把"错误码从哪来"固定在构造期。调用方只写 `throw new ServiceException("消息幂等异常")`（真实调用点 `framework/.../idempotent/IdempotentConsumeAspect.java:74`），错误码自动落到 `B000001`（`BaseErrorCode.java:108`）；想换码就多传一个 `IErrorCode` 参数。

**不用它会怎样**：直接 `throw new RuntimeException("...")`——`GlobalExceptionHandler` 只能落到 `Throwable` 兜底（`:145`），用户看到 `B000001 系统执行出错` 这种**无区分度**的文案，A/B/C 的分流统计全部失效（⑩反例1）。

**代价**：① 三个子类的构造器一共 10 个（见 ③ 表），**重载多**、易混淆（`ClientException(String)` 与 `ClientException(String, IErrorCode)` 语义不同）；② 默认错误码是"隐式行为"——`new ServiceException(msg)` 会悄悄用 `B000001`，读者不看源码不知道；③ 异常族一旦对外暴露（`errorCode` 是 `public final`），**改码就是改契约**。


## ⑤ 批前两个内部清单

#### 5.1 外部调用穿透清单（本批用到的"别人的东西"）

| # | 调用点 | 属于谁 | 穿透到哪层 | 证据出处 | 状态 |
|---|---|---|---|---|---|
| 1 | `@Data` / `@Accessors(chain = true)` | Lombok | L1：编译期生成 getter/setter 与**返回 this 的链式 setter** | `Result.java:36-37`；⑧卡1 L1 | ✅ 本批穿透 |
| 2 | `@Getter` | Lombok | L1：为 `final` 字段生成 getter（`getErrorCode`/`getErrorMessage`） | `AbstractException.java:29`；被 `Results.java:61` 使用 | ✅ 本批穿透 |
| 3 | `implements Serializable` + `@Serial` | JDK 序列化 | L1：跨进程/缓存传递时的兼容性标记 | `Result.java:38-41` | ✅ 本批穿透（⑩反例6） |
| 4 | `Optional.ofNullable(...).orElse(...)` | JDK | L1：null 安全的**回退**语义 | `AbstractException.java:39`、`ServiceException.java:45` | ✅ 本批穿透 |
| 5 | `StringUtils.hasLength` | Spring Core | L1：空串与 null 一起判 | `AbstractException.java:22`/`:39` | ✅ 本批穿透 |
| 6 | `@ExceptionHandler` + `MethodArgumentNotValidException` | Spring MVC | L2：异常派发按"最具体匹配"选处理器 | `GlobalExceptionHandler.java:61`/`:92`/`:145`；⑧卡2 L1 | ✅ 本批穿透（L2） |
| 7 | `NotLoginException` / `NotRoleException` | Sa-Token | L1：认证授权异常被单独翻译成信封 | `GlobalExceptionHandler.java:111`/`:120` | ↩ 已讲回链（阶段3 认证批次） |
| 8 | `slf4j` 的 `log.error/warn` | SLF4J | L1：失败日志分级（业务失败 warn、系统失败 error） | `GlobalExceptionHandler.java:95`/`:104`/`:113`/`:147` | ✅ 本批穿透 |
| 9 | `HttpServletRequest.getMethod()/getRequestURL()` | Servlet API | L1：日志里带方法与 URL | `GlobalExceptionHandler.java:95`/`:151` | ✅ 本批穿透 |

#### 5.2 讲解骨架清单（填完再写正文）

| 文件 | 业务镜头 | 架构位置 | 实现要点 | 调用链 | 失败场景 | 测试视角 | Vibecoding 视角 | 验证证据 |
|---|---|---|---|---|---|---|---|---|
| `Result.java`★ | "前端只看一个字段" | framework/convention，所有响应的形状 | 4 字段 + 成功码常量 + `isSuccess()`；链式 setter | ⑦.1 第 7~8 跳 | 手搓 `new Result<>()` 漏 code（⑩反例3） | 无直测（⑪ 已声明） | 1 错误码契约必须稳定 | ⑬.1 闸门 PASS |
| `AbstractException.java`★ | "把错误码装进异常" | framework/exception 基类 | `public final` 字段 + 构造期翻译 + message 回退 | ⑦.1 第 3~4 跳 | 丢 `cause` → 堆栈断链（⑩反例4） | 无直测 | 2 既有资产：`IErrorCode` 接口 | 40 行、注入 41 行 |
| `ClientException.java` | "用户改一下输入就行" | A 段失败 | 4 构造器 + toString 契约 | ⑦.1 第 2 跳 | 该 4xx 的算成 5xx（⑩反例5） | 无直测 | ⑫6 审查：码段与语义一致 | 真实调用点 5+ 处 |
| `RemoteException.java` | "第三方挂了，别怪我们" | C 段失败 | 3 构造器（无 `IErrorCode`-only 重载） | ⑦.1 第 2~4 跳 | 语义混用（⑩反例5） | 无直测 | ⑫6 审查：三段码前缀 | 48 行 |
| `ServiceException.java` | "我们的锅，要能定位" | B 段失败 | 4 构造器 + `Optional` 兜 null message | ⑦.1 第 2~4 跳 | null message 混进响应（⑩反例3 的变体） | 无直测 | ⑫7 实验：把码段改错看兜底 | 55 行 |


#### 6.1 `Result.java`★ —— 91 行定义一个"所有接口都必须长这样"的外层

**本文件要解决的一个问题**：前端怎么用**一套**解析逻辑处理所有接口的成功与失败？输入：业务数据（或什么都没有）；输出：`{code, message, data, requestId}` 四字段 JSON。

**白话开场**：这 91 行里真正的"设计"只有三处——`SUCCESS_CODE = "0"`（成功只有一种写法）、四个字段（少一个前端就要特殊处理）、`isSuccess()`（把"成功"这件事收进类里，而不是让每个人自己判 `"0".equals(code)`）。其余是 Lombok 注解与 Javadoc。看懂它，你就明白为什么本仓**禁止手搓 `new Result<>()`**。

**构造方式与手法**：**没人 `new` 它两次**——业务代码通过 `Results` 工厂（`Results.java:34`/`:42`/`:51`/`:60`）拿到实例，工厂保证 `code` 一定被设过；`Result` 自身是 `@Data` + `@Accessors(chain = true)` 的**可变链式对象**（不是 record/不可变对象），生命周期是"一次请求一次"，随响应序列化后即丢。
手法上是"**信封 + 常量 + 判定方法**"三件套：把"成功"这一语义**从字符串字面量提升为类内常量**（`SUCCESS_CODE`），代价是它仍是 `String` 而非枚举——类型安全靠约定而非编译器（⑩反例2）。

```java
/*  // :L1
 * Licensed to the Apache Software Foundation (ASF) under one or more  // :L2
 * contributor license agreements.  See the NOTICE file distributed with  // :L3
 * this work for additional information regarding copyright ownership.  // :L4
 * The ASF licenses this file to You under the Apache License, Version 2.0  // :L5
 * (the "License"); you may not use this file except in compliance with  // :L6
 * the License.  You may obtain a copy of the License at  // :L7
 *  // :L8
 *     http://www.apache.org/licenses/LICENSE-2.0  // :L9
 *  // :L10
 * Unless required by applicable law or agreed to in writing, software  // :L11
 * distributed under the License is distributed on an "AS IS" BASIS,  // :L12
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  // :L13
 * See the License for the specific language governing permissions and  // :L14
 * limitations under the License.  // :L15
 */  // :L16

package com.nageoffer.ai.ragent.framework.convention;  // :L18  ←教材：包名直译「约定」：这里放跨模块的对外契约，不放业务

import lombok.Data;  // :L20  ←教材：Lombok @Data：生成 getter/setter/equals/hashCode/toString
import lombok.experimental.Accessors;  // :L21  ←教材：Lombok @Accessors：chain=true 让 setter 返回 this（链式装配的前提）

import java.io.Serial;  // :L23  ←教材：@Serial 注解：显式声明序列化版本号字段
import java.io.Serializable;  // :L24  ←教材：Serializable：信封要能跨进程/缓存传递

/**  // :L26  ←教材：类 Javadoc 写明「所有接口返回都应使用此对象包装」——这是契约文字
 * 全局统一返回结果对象  // :L27
 *  // :L28
 * <p>  // :L29
 * 用于规范化所有 API 接口的返回格式，确保前后端交互的一致性  // :L30
 * 所有接口返回都应使用此对象包装，避免不同开发人员定义不一致的返回结构  // :L31
 * </p>  // :L32
 *  // :L33
 * @param <T> 响应数据的类型  // :L34
 */  // :L35  ←教材：泛型 T 即载荷类型：成功与失败共用同一个外层
@Data  // :L36  ←教材：@Data 生成访问器；本类无显式构造器，靠默认无参构造（工厂才能 new）
@Accessors(chain = true)  // :L37  ←教材：chain=true：才有 new Result<Void>().setCode(...).setData(...) 的写法
public class Result<T> implements Serializable {  // :L38  ←教材：class Result<T> implements Serializable：形状 + 序列化契约

    @Serial  // :L40
    private static final long serialVersionUID = 5679018624309023727L;  // :L41  ←教材：显式 serialVersionUID：字段增删后反序列化旧数据会报错而不是静默错位

    /**  // :L43
     * 成功状态码  // :L44
     * <p>  // :L45
     * 当接口请求成功时，返回此状态码  // :L46
     * </p>  // :L47
     */  // :L48
    public static final String SUCCESS_CODE = "0";  // :L49  ←教材：SUCCESS_CODE = "0"：成功码定义在此，改它等于改对外契约

    /**  // :L51
     * 状态码  // :L52
     * <p>  // :L53
     * 标识请求的处理结果，{@code "0"} 表示成功，其他值表示各类错误或异常情况  // :L54
     * </p>  // :L55
     */  // :L56
    private String code;  // :L57  ←教材：字段 code：注释写明 "0" 表示成功、其他值表示各类错误

    /**  // :L59
     * 响应消息  // :L60
     * <p>  // :L61
     * 对本次请求结果的文字描述，成功时可为成功提示，失败时为错误原因说明  // :L62
     * </p>  // :L63
     */  // :L64
    private String message;  // :L65  ←教材：字段 message：给人看的文案（失败原因说明）

    /**  // :L67
     * 响应数据  // :L68
     * <p>  // :L69
     * 接口返回的业务数据，类型由泛型 T 指定。请求失败时可能为 {@code null}  // :L70
     * </p>  // :L71
     */  // :L72
    private T data;  // :L73  ←教材：字段 data：泛型载荷；Javadoc 写明失败时可能为 null

    /**  // :L75
     * 请求追踪 ID  // :L76
     * <p>  // :L77
     * 用于链路追踪和问题排查，每个请求具有唯一的标识符  // :L78
     * </p>  // :L79
     */  // :L80
    private String requestId;  // :L81  ←教材：字段 requestId：追踪号，让「用户截图」对得上「服务端日志」

    /**  // :L83
     * 判断请求是否成功  // :L84
     *  // :L85
     * @return 如果状态码为 {@link #SUCCESS_CODE}，返回 {@code true}；否则返回 {@code false}  // :L86
     */  // :L87
    public boolean isSuccess() {  // :L88  ←教材：isSuccess()：把「成功」收进类里，前端不必自己判字符串
        return SUCCESS_CODE.equals(code);  // :L89  ←教材：常量在前比较：code 为 null 时返回 false，天然 null-safe
    }  // :L90
}  // :L91
```

**逐行要点表**：

| 行 | 讲解 |
|---|---|
| :18 | `package …framework.convention` —— 包名直译是"约定"：这里放的是**跨模块的对外约定**，不放业务 |
| :20-21 | `import lombok.Data` / `lombok.experimental.Accessors` —— 两个注解决定了后面所有 getter/setter 的存在与形状 |
| :23-24 | `java.io.Serial` / `Serializable` —— 信封要能被序列化（跨进程、缓存、消息），见 ⑩反例6 |
| :26-35 | 类 Javadoc：写明"所有接口返回都应使用此对象包装"——**这是契约文字，不是建议** |
| :36 | `@Data` —— 生成 getter/setter/`equals`/`hashCode`/`toString`；**没有无参构造器时它不会自动造**（本类没有显式构造器，靠默认无参构造 ✓，这正是 `Results` 能 `new Result<Void>()` 的原因） |
| :37 | `@Accessors(chain = true)` —— setter 返回 `this`，才有 `new Result<Void>().setCode(...).setData(...)` 的写法（`Results.java:35-36`） |
| :38 | `class Result<T> implements Serializable` —— 泛型 `T` 是载荷类型；`Serializable` 是序列化契约 |
| :40-41 | `@Serial` + `serialVersionUID = 5679018624309023727L` —— 显式版本号：字段增删后反序列化旧数据会抛 `InvalidClassException` 而不是静默错位 |
| :43-49 | `SUCCESS_CODE = "0"` —— 成功码定义在此；改成 `"200"` 会让所有前端判定失效（**它是契约**） |
| :51-57 | 字段 `code`：注释明确"`"0"` 表示成功，其他值表示各类错误" |
| :59-65 | 字段 `message`：给人看的文案（失败原因说明） |
| :67-73 | 字段 `data`：泛型载荷；Javadoc 写明"请求失败时可能为 `null`" |
| :75-81 | 字段 `requestId`：链路追踪标识；它是"用户截图 ↔ 服务端日志"的桥 |
| :83-90 | `isSuccess()`：`SUCCESS_CODE.equals(code)` —— 用常量在前比较，天然 null-safe（`code` 为 null 时返回 false 而不抛 NPE） |
| :91 | 类收尾：无业务逻辑、无静态工厂（工厂在 `Results`，见 ③ 关联件表） |

**边界与副作用**：

- **边界**：`Result` 只管"形状"，**不管 HTTP 状态码**——失败时状态码由 `GlobalExceptionHandler` 决定（本仓业务失败仍返回 200，见 ⑩反例2）。
- **副作用**：`@Data` 会生成 `setCode/setMessage/setData/setRequestId`——**信封可以在任何地方被改**（包括 Handler 返回之后、序列化之前）。本仓靠"只由 `Results` 构造"这个约定约束，而不是靠不可变设计。
- **风险点**：`data` 泛型在**反序列化**时会擦除（拿到 `LinkedHashMap` 而不是目标类型）；`serialVersionUID` 一旦改动，所有旧缓存数据作废。

**【讲解】为什么用"信封类 + 静态工厂"，而不是裸 DTO、也不是 `ResponseEntity`**：

- **问题聚焦**：失败信息放哪？三种位置——HTTP 状态码里、信封字段里、两者都放。
- **本仓选择**：只放信封（`code`），HTTP 层保持"能通就 200"。**收益**：前端一处判断（`isSuccess()`），网关/客户端不会把业务失败当传输失败重试；**代价**：与 HTTP 语义脱钩，监控要专门看 body。
- **替代方案对比**：① `ResponseEntity<Result<T>>`（状态码 + 信封都管）——语义最正，但每个 Controller 都要手写状态码映射，且**异常路径**（`@ExceptionHandler` 返回什么状态码？）要再定一套规则；本仓用 `Result<Void>` 做统一返回类型，把状态码决策收敛到一个 Handler 里。② 裸 DTO + 约定字段——最省事，但"约定"不可校验，前端要逐接口适配（4.1 对比表）。③ `record`（不可变）——更安全，但本仓要链式 setter 与 Jackson 反序列化，`record` 需要 `@JsonCreator` 等额外配置。
- **一句话可记忆**：**信封把"成功/失败"变成类内常量与类内方法，前端就从"猜"变成"判"**。

**【怎么用】**（调用现场）

- 调用点：`Result` 自身只被"工厂 + Handler"构造；真实调用点（用 `git grep -n "Results\."` 扫出，不凭印象）：`agent/.../AgentChatController.java:55`（`Results.success()`）、`agent/.../AgentConversationController.java:50`/`:55`/`:62`（`Results.success(data)`）——**生产里成功响应只走 `Results.success` 这一条路**；失败响应只走 `GlobalExceptionHandler`（`Results.failure`，`Results.java:60`）。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```text
成功（无载荷）：   return Results.success();
成功（带载荷）：   return Results.success(conversationVO);
失败：             throw new ClientException("会话不存在");   // 由 Handler 翻译成 failure 信封
前端判定：         if (!body.isSuccess()) { 按 code 首位分流 A/B/C }
```

- 传进去什么形态 / 拿回来什么形态：传"业务对象或空"；拿回"`Result<T>` 实例（含 code/message/data/requestId）"，HTTP 层再由框架序列化。

**【上下游】**（契约）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游调用方 | `Results.success()` / `failure()`（`Results.java:34`/`:51`/`:60`） | 业务数据或 `null` | 手搓 `new Result<>()` → `code` 为 `null` → 前端判失败（⑩反例3） |
| 下游消费方 | Spring MVC 消息转换器（Jackson）→ 前端 | `Result<T>` 序列化为 JSON | 泛型擦除 → `data` 变 `LinkedHashMap`；`serialVersionUID` 不匹配 → `InvalidClassException` |

**【怎么接】**（信封要加字段时）

1. **要覆写/继承什么**：不继承——接入方式是**改这个类**（加字段）**或**在 `Results` 加工厂方法；**不要**在业务模块里新建第二个信封类。
2. **最小可编译实现**：加字段照现有风格（`@Data` 已生成访问器，无需手写）：

```java
// 教学合成片段：新增一个字段（真实改动应同步前端解析与文档）
private String traceId;      // 与 requestId 的区别：traceId 跨服务，requestId 单次请求
```

3. **注册/装配路径**：**无需注册**（`Result` 是普通 POJO）；但"它能被序列化"依赖 Jackson 自动配置（`WebAutoConfiguration` 注册 `GlobalExceptionHandler` 与消息转换器）。
4. **扩展步骤（≥3 条）**：
   1. 先定字段语义与**是否可空**（本仓 `data` 明确"失败时可能为 null"）；
   2. 改 `Result` 后**同步 `Results` 工厂**（否则新字段永远不被赋值）；
   3. 更新前端解析与接口文档（信封字段是**对外契约**，属于破坏性变更）；
   4. 验证：找一条成功接口与一条失败接口各打一次，确认新字段在两种路径都出现——**只测成功路径会漏掉失败路径**。
5. **会咬人的地方**：① `@Data` 生成 `equals/hashCode`，把 `Result` 当 Map 的 key 会随字段变化而漂移；② 泛型反序列化需 `TypeReference`；③ 加字段后旧缓存/旧消息体反序列化可能因 `serialVersionUID` 未变而"字段为 null"。

---
