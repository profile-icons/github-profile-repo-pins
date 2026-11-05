use super::{Ancestry, Commit, Mask};
use crate::hash::sha256_hex as digest;
use rustpython_ast::{self as ast, Fold, Ranged, fold, text_size::TextRange};
use rustpython_parser::{Mode, Parse, Tok, lexer};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    convert::Infallible,
    sync::Arc,
};

const MIN_NODES: usize = 40;
const MIN_STATEMENTS: usize = 3;
const MAX_SRC_BYTES: usize = 1_000_000;
#[derive(Default)]
struct Canonical {
    strip_bodies: bool,
    count: usize,
}
impl Fold<TextRange> for Canonical {
    type TargetU = ();
    type Error = Infallible;
    type UserContext = ();
    fn will_map_user(&mut self, _range: &TextRange) {}
    fn map_user(&mut self, _range: TextRange, _context: ()) -> std::result::Result<(), Infallible> {
        Ok(())
    }
    fn fold_stmt(&mut self, mut node: ast::Stmt) -> std::result::Result<ast::Stmt<()>, Infallible> {
        self.count += 1;
        if self.strip_bodies {
            clear_bodies(&mut node);
        }
        fold::fold_stmt(self, node)
    }
    fn fold_expr(&mut self, node: ast::Expr) -> std::result::Result<ast::Expr<()>, Infallible> {
        self.count += 1;
        fold::fold_expr(self, node)
    }
    fn fold_expr_context(
        &mut self,
        node: ast::ExprContext,
    ) -> std::result::Result<ast::ExprContext, Infallible> {
        self.count += 1;
        Ok(node)
    }
    fn fold_operator(
        &mut self,
        node: ast::Operator,
    ) -> std::result::Result<ast::Operator, Infallible> {
        self.count += 1;
        Ok(node)
    }
    fn fold_boolop(&mut self, node: ast::BoolOp) -> std::result::Result<ast::BoolOp, Infallible> {
        self.count += 1;
        Ok(node)
    }
    fn fold_unaryop(
        &mut self,
        node: ast::UnaryOp,
    ) -> std::result::Result<ast::UnaryOp, Infallible> {
        self.count += 1;
        Ok(node)
    }
    fn fold_cmpop(&mut self, node: ast::CmpOp) -> std::result::Result<ast::CmpOp, Infallible> {
        self.count += 1;
        Ok(node)
    }
    fn fold_arguments(
        &mut self,
        node: ast::Arguments,
    ) -> std::result::Result<ast::Arguments<()>, Infallible> {
        self.count += 1;
        fold::fold_arguments(self, node)
    }
    fn fold_arg(&mut self, node: ast::Arg) -> std::result::Result<ast::Arg<()>, Infallible> {
        self.count += 1;
        fold::fold_arg(self, node)
    }
    fn fold_keyword(
        &mut self,
        node: ast::Keyword,
    ) -> std::result::Result<ast::Keyword<()>, Infallible> {
        self.count += 1;
        fold::fold_keyword(self, node)
    }
    fn fold_alias(&mut self, node: ast::Alias) -> std::result::Result<ast::Alias<()>, Infallible> {
        self.count += 1;
        fold::fold_alias(self, node)
    }
    fn fold_comprehension(
        &mut self,
        node: ast::Comprehension,
    ) -> std::result::Result<ast::Comprehension<()>, Infallible> {
        self.count += 1;
        fold::fold_comprehension(self, node)
    }
    fn fold_withitem(
        &mut self,
        node: ast::WithItem,
    ) -> std::result::Result<ast::WithItem<()>, Infallible> {
        self.count += 1;
        fold::fold_withitem(self, node)
    }
    fn fold_match_case(
        &mut self,
        node: ast::MatchCase,
    ) -> std::result::Result<ast::MatchCase<()>, Infallible> {
        self.count += 1;
        fold::fold_match_case(self, node)
    }
    fn fold_pattern(
        &mut self,
        node: ast::Pattern,
    ) -> std::result::Result<ast::Pattern<()>, Infallible> {
        self.count += 1;
        fold::fold_pattern(self, node)
    }
    fn fold_excepthandler(
        &mut self,
        node: ast::ExceptHandler,
    ) -> std::result::Result<ast::ExceptHandler<()>, Infallible> {
        self.count += 1;
        fold::fold_excepthandler(self, node)
    }
    fn fold_type_param(
        &mut self,
        node: ast::TypeParam,
    ) -> std::result::Result<ast::TypeParam<()>, Infallible> {
        self.count += 1;
        fold::fold_type_param(self, node)
    }
}
fn clear_bodies(node: &mut ast::Stmt) {
    match node {
        ast::Stmt::FunctionDef(node) => node.body.clear(),
        ast::Stmt::AsyncFunctionDef(node) => node.body.clear(),
        ast::Stmt::ClassDef(node) => node.body.clear(),
        ast::Stmt::For(node) => {
            node.body.clear();
            node.orelse.clear();
        }
        ast::Stmt::AsyncFor(node) => {
            node.body.clear();
            node.orelse.clear();
        }
        ast::Stmt::While(node) => {
            node.body.clear();
            node.orelse.clear();
        }
        ast::Stmt::If(node) => {
            node.body.clear();
            node.orelse.clear();
        }
        ast::Stmt::With(node) => node.body.clear(),
        ast::Stmt::AsyncWith(node) => node.body.clear(),
        ast::Stmt::Match(node) => {
            for case in &mut node.cases {
                case.body.clear();
            }
        }
        ast::Stmt::Try(node) => {
            node.body.clear();
            node.orelse.clear();
            node.finalbody.clear();
            for handler in &mut node.handlers {
                let ast::ExceptHandler::ExceptHandler(handler) = handler;
                handler.body.clear();
            }
        }
        ast::Stmt::TryStar(node) => {
            node.body.clear();
            node.orelse.clear();
            node.finalbody.clear();
            for handler in &mut node.handlers {
                let ast::ExceptHandler::ExceptHandler(handler) = handler;
                handler.body.clear();
            }
        }
        _ => {}
    }
}
fn canonical(node: &ast::Stmt, header: bool) -> (String, usize) {
    let mut folder: Canonical = Canonical {
        strip_bodies: header,
        count: 0,
    };
    let norm: ast::Stmt<()> = folder
        .fold_stmt(node.clone())
        .unwrap_or_else(|never| match never {});
    (format!("{norm:?}"), folder.count)
}
#[derive(Clone)]
struct Leaf {
    start: usize,
    end: usize,
    start_col: usize,
    end_col: usize,
    weight: usize,
}
#[derive(Clone)]
struct Function {
    exact: String,
    sig: String,
    weight: usize,
    start: usize,
    end: usize,
    leaves: BTreeMap<String, Vec<Leaf>>,
}
struct Snapshot {
    lines: Vec<String>,
    comments: BTreeSet<usize>,
    exact: String,
    weight: usize,
    funcs: Vec<Function>,
}
struct Origin {
    commit: usize,
    snapshot: Arc<Snapshot>,
    func: Option<usize>,
}

fn suites(node: &ast::Stmt) -> Vec<(&'static str, &[ast::Stmt])> {
    match node {
        ast::Stmt::FunctionDef(node) => vec![("body", &node.body)],
        ast::Stmt::AsyncFunctionDef(node) => vec![("body", &node.body)],
        ast::Stmt::ClassDef(node) => vec![("body", &node.body)],
        ast::Stmt::For(node) => vec![("body", &node.body), ("orelse", &node.orelse)],
        ast::Stmt::AsyncFor(node) => vec![("body", &node.body), ("orelse", &node.orelse)],
        ast::Stmt::While(node) => vec![("body", &node.body), ("orelse", &node.orelse)],
        ast::Stmt::If(node) => vec![("body", &node.body), ("orelse", &node.orelse)],
        ast::Stmt::With(node) => vec![("body", &node.body)],
        ast::Stmt::AsyncWith(node) => vec![("body", &node.body)],
        ast::Stmt::Match(node) => node
            .cases
            .iter()
            .map(|case| ("cases", case.body.as_slice()))
            .collect(),
        ast::Stmt::Try(node) => std::iter::once(("body", node.body.as_slice()))
            .chain(node.handlers.iter().map(|handler| {
                let ast::ExceptHandler::ExceptHandler(handler) = handler;
                ("handlers", handler.body.as_slice())
            }))
            .chain([
                ("orelse", node.orelse.as_slice()),
                ("finalbody", node.finalbody.as_slice()),
            ])
            .collect(),
        ast::Stmt::TryStar(node) => std::iter::once(("body", node.body.as_slice()))
            .chain(node.handlers.iter().map(|handler| {
                let ast::ExceptHandler::ExceptHandler(handler) = handler;
                ("handlers", handler.body.as_slice())
            }))
            .chain([
                ("orelse", node.orelse.as_slice()),
                ("finalbody", node.finalbody.as_slice()),
            ])
            .collect(),
        _ => Vec::new(),
    }
}
fn row(src: &str, offset: usize) -> usize {
    src.as_bytes()[..offset.min(src.len())]
        .iter()
        .filter(|byte| **byte == b'\n')
        .count()
        + 1
}
fn column(src: &str, offset: usize) -> usize {
    src.as_bytes()[..offset.min(src.len())]
        .iter()
        .rposition(|byte| *byte == b'\n')
        .map_or(offset, |newline| offset - newline - 1)
}
fn leaf(node: &ast::Stmt, src: &str, scope: &str, res: &mut BTreeMap<String, Vec<Leaf>>) {
    if matches!(
        node,
        ast::Stmt::FunctionDef(_) | ast::Stmt::AsyncFunctionDef(_) | ast::Stmt::ClassDef(_)
    ) {
        return;
    }
    let children: Vec<(&str, &[ast::Stmt])> = suites(node);
    if children.iter().all(|(_, nodes)| nodes.is_empty()) {
        let (text, weight): (String, usize) = canonical(node, false);
        let start: usize = u32::from(node.start()) as usize;
        let end: usize = u32::from(node.end()) as usize;
        res.entry(digest(&format!("{scope}\0{text}")))
            .or_default()
            .push(Leaf {
                start: row(src, start),
                end: row(src, end),
                start_col: column(src, start),
                end_col: column(src, end),
                weight,
            });
    } else {
        let header: String = canonical(node, true).0;
        for (field, nodes) in children {
            for child in nodes {
                leaf(child, src, &format!("{scope}\0{header}\0{field}"), res);
            }
        }
    }
}
fn visit(node: &ast::Stmt, src: &str, context: &str, res: &mut Vec<Function>) {
    let (text, weight): (String, usize) = canonical(node, false);
    let header: String = canonical(node, true).0;
    let function: bool = matches!(
        node,
        ast::Stmt::FunctionDef(_) | ast::Stmt::AsyncFunctionDef(_)
    );
    if function {
        let mut leaves: BTreeMap<String, Vec<Leaf>> = BTreeMap::new();
        for (_, body) in suites(node) {
            for statement in body {
                leaf(statement, src, "body", &mut leaves);
            }
        }
        let decorators: &[ast::Expr] = match node {
            ast::Stmt::FunctionDef(node) => &node.decorator_list,
            ast::Stmt::AsyncFunctionDef(node) => &node.decorator_list,
            _ => &[],
        };
        let start: usize = decorators
            .iter()
            .map(|node| u32::from(node.start()) as usize)
            .chain(std::iter::once(u32::from(node.start()) as usize))
            .min()
            .unwrap_or(0);
        res.push(Function {
            exact: digest(&format!("{context}\0{text}")),
            sig: digest(&format!("{context}\0{header}")),
            weight,
            start: row(src, start),
            end: row(src, u32::from(node.end()) as usize),
            leaves,
        });
    }
    for (field, nodes) in suites(node) {
        for child in nodes {
            visit(child, src, &format!("{context}\0{header}\0{field}"), res);
        }
    }
}
fn parse(src: &str) -> Option<Snapshot> {
    if src.len() > MAX_SRC_BYTES {
        return None;
    }
    let nodes: Vec<ast::Stmt> = ast::Suite::parse(src, "<snapshot>").ok()?;
    let mut comments: BTreeSet<usize> = BTreeSet::new();
    for token in lexer::lex(src, Mode::Module) {
        let (token, range): (Tok, TextRange) = token.ok()?;
        if matches!(token, Tok::Comment(_)) {
            comments.insert(row(src, u32::from(range.start()) as usize));
        }
    }
    let mut funcs: Vec<Function> = Vec::new();
    let mut exact: String = String::new();
    let mut weight: usize = 1;
    for node in nodes {
        let (text, count): (String, usize) = canonical(&node, false);
        exact.push_str(&text);
        weight += count;
        visit(&node, src, "body", &mut funcs);
    }
    Some(Snapshot {
        lines: src.lines().map(str::to_owned).collect(),
        comments,
        exact: digest(&exact),
        weight,
        funcs,
    })
}
pub(crate) fn exclusions(commits: &[Commit], ancestry: &mut Ancestry<'_>) -> Vec<Mask> {
    let mut res: Vec<Mask> = vec![Mask::new(); commits.len()];
    let mut cache: HashMap<String, Option<Arc<Snapshot>>> = HashMap::new();
    let mut origins: Vec<Origin> = Vec::new();
    let mut exact: HashMap<String, Vec<usize>> = HashMap::new();
    let mut sigs: HashMap<String, Vec<usize>> = HashMap::new();
    let mut modules: HashMap<String, Vec<usize>> = HashMap::new();
    for (idx, commit) in commits.iter().enumerate() {
        let mut pending: Vec<(String, Arc<Snapshot>)> = Vec::new();
        for (path, src) in &commit.snapshots {
            let snapshot: Option<Arc<Snapshot>> = cache
                .entry(digest(src))
                .or_insert_with(|| parse(src).map(Arc::new))
                .clone();
            let Some(snapshot) = snapshot else {
                continue;
            };
            let locations: BTreeMap<usize, usize> = commit
                .additions
                .iter()
                .enumerate()
                .filter_map(|(addition_idx, addition)| {
                    if addition.key.0 != *path {
                        return None;
                    }
                    let line: usize = addition.row?;
                    let text: &str = if path.to_lowercase().ends_with(".ipynb") {
                        addition.key.1.strip_prefix("[code] ")?
                    } else {
                        &addition.key.1
                    };
                    (line > 0
                        && snapshot.lines.get(line - 1).is_some_and(|src| src == text)
                        && !text.trim().is_empty()
                        && !snapshot.comments.contains(&line))
                    .then_some((addition_idx, line))
                })
                .collect();
            let mut covered: BTreeSet<usize> = BTreeSet::new();
            let mut record = |lines: &BTreeSet<usize>| -> () {
                for (addition, line) in &locations {
                    if lines.contains(line) && covered.insert(*addition) {
                        *res[idx]
                            .entry(commit.additions[*addition].key.clone())
                            .or_default() += 1;
                    }
                }
            };
            let module_match: bool = modules
                .get(&snapshot.exact)
                .into_iter()
                .flatten()
                .any(|origin| ancestry.contains(origins[*origin].commit, idx));
            if module_match {
                record(&locations.values().copied().collect());
            } else {
                for func in snapshot
                    .funcs
                    .iter()
                    .filter(|func| func.weight >= MIN_NODES)
                {
                    let full_match: bool = exact
                        .get(&func.exact)
                        .into_iter()
                        .flatten()
                        .any(|origin| ancestry.contains(origins[*origin].commit, idx));
                    if full_match {
                        record(&(func.start..=func.end).collect());
                        continue;
                    }
                    for candidate in sigs.get(&func.sig).into_iter().flatten() {
                        let origin: &Origin = &origins[*candidate];
                        if !ancestry.contains(origin.commit, idx) {
                            continue;
                        }
                        let Some(func_idx) = origin.func else {
                            continue;
                        };
                        let original: &Function = &origin.snapshot.funcs[func_idx];
                        let shared: Vec<&String> = func
                            .leaves
                            .keys()
                            .filter(|key| original.leaves.contains_key(*key))
                            .collect();
                        if shared.len() < MIN_STATEMENTS
                            || shared
                                .iter()
                                .map(|key| func.leaves[*key][0].weight)
                                .sum::<usize>()
                                < MIN_NODES
                        {
                            continue;
                        }
                        let mut lines: BTreeSet<usize> = BTreeSet::new();
                        for key in shared {
                            for leaf in &func.leaves[key] {
                                for line in leaf.start..=leaf.end {
                                    let text: &str = &snapshot.lines[line - 1];
                                    if line == leaf.start
                                        && !text
                                            .get(..leaf.start_col)
                                            .unwrap_or(text)
                                            .trim()
                                            .is_empty()
                                    {
                                        continue;
                                    }
                                    if line == leaf.end
                                        && !text
                                            .get(leaf.end_col..)
                                            .unwrap_or(text)
                                            .trim()
                                            .is_empty()
                                    {
                                        continue;
                                    }
                                    lines.insert(line);
                                }
                            }
                        }
                        record(&lines);
                    }
                }
            }
            pending.push((path.clone(), snapshot));
        }
        for (_path, snapshot) in pending {
            if snapshot.weight >= MIN_NODES {
                modules
                    .entry(snapshot.exact.clone())
                    .or_default()
                    .push(origins.len());
                origins.push(Origin {
                    commit: idx,
                    snapshot: Arc::clone(&snapshot),
                    func: None,
                });
            }
            for (func_idx, func) in snapshot
                .funcs
                .iter()
                .enumerate()
                .filter(|(_, func)| func.weight >= MIN_NODES)
            {
                let origin_idx: usize = origins.len();
                exact
                    .entry(func.exact.clone())
                    .or_default()
                    .push(origin_idx);
                sigs.entry(func.sig.clone()).or_default().push(origin_idx);
                origins.push(Origin {
                    commit: idx,
                    snapshot: Arc::clone(&snapshot),
                    func: Some(func_idx),
                });
            }
        }
    }
    res
}
