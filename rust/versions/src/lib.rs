use proc_macro::{Delimiter, Group, Ident, Punct, Spacing, Span, TokenStream, TokenTree};


//use crate::helpers::expect_punct;

fn expect_group(it: &mut impl Iterator<Item = TokenTree>) -> Group {
    if let Some(TokenTree::Group(group)) = it.next() {
        group
    } else {
        panic!("Expected Group")
    }
}

fn expect_punct(it: &mut impl Iterator<Item = TokenTree>) -> String {
    if let Some(TokenTree::Punct(punct)) = it.next() {
        punct.to_string()
    } else {
        panic!("Expected Group")
    }
}

fn drop_until_punct(it: &mut impl Iterator<Item = TokenTree>, delimiter: &str, is_struct: bool) {
    let mut depth: isize = 0;
    let mut colons: isize = 0;
    for token in it.by_ref() {
        if let TokenTree::Punct(punct) = token {
            match punct.as_char() {
                ':' => {
                    colons += 1;
                }
                '<' => {
                    if depth > 0 || colons == 2 || is_struct {
                        depth += 1;
                    }
                    colons = 0;
                }
                '>' => {
                    if depth > 0 {
                        depth -= 1;
                    }
                    colons = 0;
                }
                _ => {
                    colons = 0;
                    if depth == 0 && delimiter.contains(&punct.to_string()) {
                        break;
                    }
                }
            }
        }
    }
}

fn drop_until_braces(it: &mut impl Iterator<Item = TokenTree>) {
    let mut depth: isize = 0;
    let mut colons: isize = 0;
    for token in it.by_ref() {
        match token {
            TokenTree::Punct(punct) => match punct.as_char() {
                ':' => {
                    colons += 1;
                }
                '<' => {
                    if depth > 0 || colons == 2 {
                        depth += 1;
                    }
                    colons = 0;
                }
                '>' => {
                    if depth > 0 {
                        depth -= 1;
                    }
                    colons = 0;
                }
                _ => colons = 0,
            },
            TokenTree::Group(group) if group.delimiter() == Delimiter::Brace => {
                if depth == 0 {
                    break;
                }
            }
            _ => (),
        }
    }
}

struct VersionConfig {
    fields: &'static [&'static str],
    enums: &'static [&'static [&'static str]],
    versions: &'static [&'static [&'static str]],
}

static AGX_VERSIONS: VersionConfig = VersionConfig {
    fields: &["G", "V"],
    enums: &[
        &["G13", "G14", "G14X"],
        &["V12_3", "V12_4", "V13_0B4", "V13_2", "V13_3", "V13_5"],
    ],
    versions: &[
        &["G13", "V12_3"],
        &["G14", "V12_4"],
        &["G13", "V13_5"],
        &["G14", "V13_5"],
        &["G14X", "V13_5"],
    ],
};

fn check_version(
    config: &VersionConfig,
    ver: &[usize],
    it: &mut impl Iterator<Item = TokenTree>,
) -> bool {
    let first = it.next().unwrap();
    let val: bool = match &first {
        TokenTree::Group(group) => check_version(config, ver, &mut group.stream().into_iter()),
        TokenTree::Ident(ident) => {
            let key = config
                .fields
                .iter()
                .position(|&r| r == ident.to_string())
                .unwrap_or_else(|| panic!("Unknown field {}", ident));
            let mut operator = expect_punct(it);
            let mut rhs_token = it.next().unwrap();
            if let TokenTree::Punct(punct) = &rhs_token {
                operator.extend(std::iter::once(punct.as_char()));
                rhs_token = it.next().unwrap();
            }
            let rhs_name = if let TokenTree::Ident(ident) = &rhs_token {
                ident.to_string()
            } else {
                panic!("Unexpected token {}", ident)
            };

            let rhs = config.enums[key]
                .iter()
                .position(|&r| r == rhs_name)
                .unwrap_or_else(|| panic!("Unknown value for {}:{}", ident, rhs_name));
            let lhs = ver[key];

            match operator.as_str() {
                "==" => lhs == rhs,
                "!=" => lhs != rhs,
                ">" => lhs > rhs,
                ">=" => lhs >= rhs,
                "<" => lhs < rhs,
                "<=" => lhs <= rhs,
                _ => panic!("Unknown operator {}", operator),
            }
        }
        _ => {
            panic!("Unknown token {}", first)
        }
    };

    let boolop = it.next();
    match boolop {
        Some(TokenTree::Punct(punct)) => {
            let right = expect_punct(it);
            if right != punct.to_string() {
                panic!("Unexpected op {}{}", punct, right);
            }
            match punct.as_char() {
                '&' => val && check_version(config, ver, it),
                '|' => val || check_version(config, ver, it),
                _ => panic!("Unexpected op {}{}", right, right),
            }
        }
        Some(a) => panic!("Unexpected op {}", a),
        None => val,
    }
}

fn filter_versions(
    config: &VersionConfig,
    tag: &str,
    ver: &[usize],
    tree: impl IntoIterator<Item = TokenTree>,
    is_struct: bool,
) -> Vec<TokenTree> {
    let mut out = Vec::<TokenTree>::new();
    let mut it = tree.into_iter();

    while let Some(token) = it.next() {
        let mut tail: Option<TokenTree> = None;
        match &token {
            TokenTree::Punct(punct) if punct.to_string() == "#" => {
                let group = expect_group(&mut it);
                let mut grp_it = group.stream().into_iter();
                let attr = grp_it.next().unwrap();
                match attr {
                    TokenTree::Ident(ident) if ident.to_string() == "ver" => {
                        if check_version(config, ver, &mut grp_it) {
                        } else if is_struct {
                            drop_until_punct(&mut it, ",", true);
                        } else {
                            let first = it.next().unwrap();
                            match &first {
                                TokenTree::Ident(ident)
                                    if ["while", "for", "loop", "if", "match", "unsafe", "fn"]
                                        .contains(&ident.to_string().as_str()) =>
                                {
                                    drop_until_braces(&mut it);
                                }
                                TokenTree::Group(_) => (),
                                _ => {
                                    drop_until_punct(&mut it, ",;", false);
                                }
                            }
                        }
                    }
                    _ => {
                        out.push(token.clone());
                        out.push(TokenTree::Group(group.clone()));
                    }
                }
                continue;
            }
            TokenTree::Punct(punct) if punct.to_string() == ":" => {
                let next = it.next();
                match next {
                    Some(TokenTree::Punct(punct)) if punct.to_string() == ":" => {
                        let next = it.next();
                        match next {
                            Some(TokenTree::Ident(idtag)) if idtag.to_string() == "ver" => {
                                let ident = match out.pop() {
                                    Some(TokenTree::Ident(ident)) => ident,
                                    a => panic!("$ver not following ident: {:?}", a),
                                };
                                let name = ident.to_string() + tag;
                                let new_ident = Ident::new(name.as_str(), ident.span());
                                out.push(TokenTree::Ident(new_ident));
                                continue;
                            }
                            Some(a) => {
                                out.push(token.clone());
                                out.push(token.clone());
                                tail = Some(a);
                            }
                            None => {
                                out.push(token.clone());
                                out.push(token.clone());
                            }
                        }
                    }
                    Some(a) => {
                        out.push(token.clone());
                        tail = Some(a);
                    }
                    None => {
                        out.push(token.clone());
                        continue;
                    }
                }
            }
            _ => {
                tail = Some(token);
            }
        }
        match &tail {
            Some(TokenTree::Group(group)) => {
                let new_body =
                    filter_versions(config, tag, ver, group.stream().into_iter(), is_struct);
                let mut stream = TokenStream::new();
                stream.extend(new_body);
                let mut filtered_group = Group::new(group.delimiter(), stream);
                filtered_group.set_span(group.span());
                out.push(TokenTree::Group(filtered_group));
            }
            Some(token) => {
                out.push(token.clone());
            }
            None => {}
        }
    }

    out
}

/// Declares multiple variants of a structure or impl code
#[proc_macro_attribute]
pub fn versions(attr: TokenStream, item: TokenStream) -> TokenStream {
    let config = match attr.to_string().as_str() {
        "AGX" => &AGX_VERSIONS,
        _ => panic!("Unknown version group {}", attr),
    };

    let mut it = item.into_iter();
    let mut out = TokenStream::new();
    let mut body: Vec<TokenTree> = Vec::new();
    let mut is_struct = false;

    while let Some(token) = it.next() {
        match token {
            TokenTree::Punct(punct) if punct.to_string() == "#" => {
                body.push(TokenTree::Punct(punct));
                body.push(it.next().unwrap());
            }
            TokenTree::Ident(ident)
                if ["struct", "enum", "union", "const", "type"]
                    .contains(&ident.to_string().as_str()) =>
            {
                is_struct = ident.to_string() != "const";
                body.push(TokenTree::Ident(ident));
                body.push(it.next().unwrap());
                // This isn't valid syntax in a struct definition, so add it for the user
                body.push(TokenTree::Punct(Punct::new(':', Spacing::Joint)));
                body.push(TokenTree::Punct(Punct::new(':', Spacing::Alone)));
                body.push(TokenTree::Ident(Ident::new("ver", Span::call_site())));
                break;
            }
            TokenTree::Ident(ident) if ident.to_string() == "impl" => {
                body.push(TokenTree::Ident(ident));
                break;
            }
            TokenTree::Ident(ident) if ident.to_string() == "fn" => {
                body.push(TokenTree::Ident(ident));
                break;
            }
            _ => {
                body.push(token);
            }
        }
    }

    body.extend(it);

    for ver in config.versions {
        let tag = ver.join("");
        let mut ver_num = Vec::<usize>::new();
        for (i, comp) in ver.iter().enumerate() {
            let idx = config.enums[i].iter().position(|&r| r == *comp).unwrap();
            ver_num.push(idx);
        }
        out.extend(filter_versions(
            config,
            &tag,
            &ver_num,
            body.clone(),
            is_struct,
        ));
    }

    out
}
