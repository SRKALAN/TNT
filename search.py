from utils import Utils as Ut
from nltk.corpus import stopwords
stop_words_english = set(stopwords.words('english'))
stop_words_spanish = set(stopwords.words('spanish'))
stop_words={'english':stop_words_english,'spanish':stop_words_spanish}
from load import init
from fuzzywuzzy import fuzz
import requests
import json
import re
from itertools import chain
support_syntax_re=re.compile(r'\(|\)|/|"|\.|;|:|\[|\]')


env=init()
endpoint =env['azure_search_endpoint']
api_version = env['api_version']
headers = {'Content-Type': 'application/json',
        'api-key': env['api_key']}

highlight_re=re.compile("<em>(.*?)</em>")
def perform_search(lob,search_index,search_string,doc_collection,is_exclusion,is_extension,is_covered,is_condition,is_definition,is_endorsement,is_basewording,def_sub_search,user_id,super_list,word_proximity_limit,top_count,country,language,document_name):


    #spell check for single phrase search

    super_list,clauses = Ut.payload_to_super_list(super_list)

    flat_super_list = [item for sublist in super_list for item in sublist]

    flat_super_list = [item for sublist in flat_super_list for item in sublist]



    #checking if AND operator is present in the search string, if yes, the scoring algorithm should be proximity based
    if 'AND' in  search_string:
        and_operator_boolean=True
    else:
        and_operator_boolean=False


    #Work around untill the problem is addressed from the fron<t end
    search_string=search_string.replace('&','').replace('\n','').replace(':','')


    all_results=[]
    for clause_string in clauses:
        clause_string_org=clause_string

        #Work around untill the problem is addresed from the front end
        clause_string=clause_string.replace('&','').replace('\n','').replace(':','')

        search_string=search_string.replace(clause_string,'')
        clause_string=support_syntax_re.sub(' ',clause_string)
        clause_string=clause_string.replace('"','').replace('(','').replace(')','').replace(';',' ').replace(':',' ')
        search_words=clause_string.split()
        search_words = [w for w in search_words if  w.lower() not in stop_words[language]  ]
        clause_string=(' ').join(search_words)
        if is_definition:
            searchFields='definition_text'
            highlight='definition_text'

        else:
            searchFields='plain_text'
            highlight='plain_text'

        search_query = "&search={}&$count=true&highlight={}&queryType=full&searchFields={}&$top={}".format(clause_string,highlight,searchFields,top_count)
        filters="&$filter="
        if doc_collection:
            filters+="search.in(folder,'{}', ',') and ".format(doc_collection)
        if document_name:
            filters+="search.in(doc_name,'{}', ',') and ".format(document_name)

        if is_exclusion :
            filters+="IsExclusion and "
        if is_extension:
            filters+="ext_flag and "
        elif is_covered:
            filters+="not IsExclusion and "

        elif is_definition :
            filters+="definition_flag and "
        elif is_condition :
            filters+="cond_flag and "
        elif is_endorsement:
            filters+="endorsements and "
        elif is_basewording:
            filters+=" not endorsements and "





        filters+="search.in(country,'{}', ',')".format(country)
        filters+=" and language eq '{}'".format(language)
        search_query+=filters


        url = endpoint + 'indexes/{}/docs'.format(search_index) + api_version + search_query


        response  = requests.get(url, headers=headers, json=clause_string)




        out_all=[]

        out = response.json()

        if 'value' not in out:
            continue
        out_all.extend(out['value'])

        score_break=1
        while '@odata.nextLink' in out and score_break > 0.3:

            url=out['@odata.nextLink']
            response  = requests.get(url, headers=headers, json=search_string)
            out = response.json()
            score_break=out['value'][0]['@search.score']
            out_all.extend(out['value'])


        for page in out_all:
                all_results.append((page,True,clause_string,clause_string_org))



    search_string=re.sub('(\((?:\sOR\s|\sAND\s)*\))','###',search_string)

    rightRE=re.compile('(AND|OR)\s+###')
    leftRE=re.compile('###\s+(AND|OR)')

    search_string=rightRE.sub('',search_string)

    search_string=leftRE.sub('',search_string)

    search_string=re.sub(re.escape('###'),'',search_string).strip()




    #condition for keyword search, making sure that null is not searched after removing the clauses from Search string
    if len(search_string)>2 or search_string=='*':

        try:

            if is_definition:
                searchFields='definition_text'
                highlight='definition_text'
            elif def_sub_search:
                searchFields='text'
                highlight='text'
            elif is_exclusion:
                searchFields='plain_text,excl_text'
                highlight='plain_text,excl_text'
            elif is_extension:
                searchFields='plain_text,ext_text'
                highlight='plain_text,ext_text'

            elif is_condition:
                searchFields='plain_text,cond_text'
                highlight='plain_text,cond_text'

            else:
                searchFields='plain_text'
                highlight='plain_text'




            search_query = "&search={}&$count=true&highlight={}&queryType=full&searchFields={}&$top={}".format(search_string,highlight,searchFields,top_count)
            filters="&$filter="
            if doc_collection:
                filters+="search.in(folder,'{}', ',') and ".format(doc_collection)
            if document_name:
                filters+="search.in(doc_name,'{}', ',') and ".format(document_name)
            if is_exclusion :
                filters+="IsExclusion and "
            if is_extension:
                filters+="ext_flag and "

            elif is_covered:
                filters+="not IsExclusion and "
            elif is_definition :
                filters+="definition_flag and "
            elif is_condition :
                filters+="cond_flag and "

            if is_endorsement:
                filters+="endorsements and "
            elif is_basewording:
                filters+=" not endorsements and "

            filters+="search.in(country,'{}', ',')".format(country)
            filters+=" and language eq '{}'".format(language)
            search_query+=filters








            url = endpoint + 'indexes/{}/docs'.format(search_index) + api_version + search_query

            response  = requests.get(url, headers=headers, json=search_string)

            out_all=[]
            out = response.json()
            out_all.extend(out['value'])


            while '@odata.nextLink' in out:
                url=out['@odata.nextLink']
                response  = requests.get(url, headers=headers, json=search_string)
                out = response.json()

                out_all.extend(out['value'])



            keyword_results=[(item,False,'','') for item in out_all]


            all_results.extend(keyword_results)
            # return keyword_results

        except Exception as err:
            print(err)
            print('Exception in keyword search :{}'.format(out['error']))

    if not all_results:
        return{"results":[],'proximity_flag':False,'key_phrases_aggregate':[],'min_proximity':0,'max_proximity':0}

    matches_list=[]
    search_scores=[]
    proximity_scores=[]


    # print(len(all_results),'all_results')



    search_result=dict()
    first_clause_score=False
    for page,is_clause,clause_string,clause_string_org in all_results:
        search_scores.append(page['@search.score'])
        content_exl_head=False
        content_cond_head=False
        content_ext_head=False

        if '@search.highlights' in page:
            if is_clause:
                if not first_clause_score:
                    upper_limit=page["@search.score"]
                    first_clause_score=True

                if page["@search.score"] <upper_limit/1.5:

                    continue
                try:
                    match_text,clause_score=Ut.clause_search(page[searchFields],clause_string_org)
                    page['clause_score']=clause_score
                    if not match_text:
                        continue
                except Exception as err:

                    print("Exception in clause search!!!!!!!!",str(err))
                    continue
                    # match_text=('....').join(page['@search.highlights'][highlight])

            elif is_definition:
                match_text=('....').join(page['@search.highlights']['definition_text'])

            elif  def_sub_search:
                match_text=('....').join(page['@search.highlights']['text'])
            elif is_exclusion:
                try:
                    content_exl_head=True
                    match_text=('....').join(page['@search.highlights']['excl_text'])
                except:
                    match_text=('....').join(page['@search.highlights']['plain_text'])
            elif is_condition:
                try:
                    content_cond_head=True
                    match_text=('....').join(page['@search.highlights']['cond_text'])
                except:
                    match_text=('....').join(page['@search.highlights']['plain_text'])


            elif is_extension:
                try:

                    match_text=('....').join(page['@search.highlights']['ext_text'])
                    content_ext_head=True
                    # print(content_ext_head,'EXT HEAD')
                except Exception as err:
                    # print(str(err),'EXCEPT BLOCK\n\n')
                    match_text=('....').join(page['@search.highlights']['plain_text'])





            else:
                match_text=('....').join(page['@search.highlights']['plain_text'])
        else:
            match_text=''

        highlight_words=list(set(highlight_re.findall(match_text)))
        highlight_words_stopword=[word for word in highlight_words if word.lower() in stop_words[language]]
        highlight_words=[word for word in highlight_words if word.lower() not in stop_words[language]]
        highlight_words_user=highlight_words
        plain_text=page['plain_text']
        definition_text=page['definition_text']


        highlight_words_def=[]
        if is_definition:
            plain_text=definition_text
            proximity_lookup_text=definition_text
        else:
            proximity_lookup_text=plain_text


        if not is_clause:
            # super_list_flat = list(chain(*super_list))

            # flattened_super_list = [val for master_list in super_list for val in master_list]
            plain_text=plain_text.replace(':','')


            high_light_words=Ut.get_highlightWords(plain_text,flat_super_list)
            if high_light_words:
                high_light_words.sort(key=len, reverse=True)
            for word in high_light_words:
                r=re.compile(r"\s+", re.MULTILINE)
                plain_text=r.sub(" ",plain_text)
                phrase_re=re.compile(re.escape(' '+word),re.I)
                plain_text=phrase_re.sub('<em>'+word+'</em>',plain_text)
                # When the word comes inside double quotes
                plain_text=plain_text.replace("\""+word,"\""+'<em>'+word+'</em>')


            # plain_text=plain_text.replace(':','')
            # page_list=page['text'].split('###')
            # page_text_list=[]
            # for i in page_list:
            #     page_text_list.append(Ut.highlight_def1(i,highlight_words))
            # page_text=' '.join(page_text_list)
            # highlight_words=list(set(highlight_re.findall(page_text)))
            # highlight_words_def= list(set(highlight_words) - set(highlight_words_user))




            # if len(highlight_words_user)==1 and not highlight_words_stopword:
            #     for highlight_word in highlight_words_user:  #for each search word  in search crteria
            #         phrase_re=re.compile(re.escape(' '+highlight_word),re.I)
            #         plain_text=phrase_re.sub('<em>'+highlight_word+'</em>',plain_text)
            # elif len(highlight_words_user)==1 and highlight_words_stopword:
            #     word_list=plain_text.split()
            #     pos_list=[]
            #     stop_word_pos_list=[]
            #     for highlight_word in highlight_words_user:
            #         pos_list.extend([pos for pos, text in enumerate(word_list) if text == highlight_word])
            #     for stpword in highlight_words_stopword:
            #         stop_word_pos_list.extend([pos for pos, text in enumerate(word_list) if text == stpword])
            #     for pos in pos_list:
            #         for stp_pos in stop_word_pos_list:
            #             if abs(pos-stp_pos)<=2:
            #                 if '<em>' not in word_list[pos]:
            #                     word_list[pos]='<em>'+word_list[pos]+'</em>'
            #                 if '<em>' not in word_list[stp_pos]:
            #                     word_list[stp_pos]='<em>'+word_list[stp_pos]+'</em>'
            #     plain_text=' '.join(word_list)
            # else:
            #     for search_words in flat_super_list:  #for each search word  in search crteria
            #         search_word_split=search_words.split()
            #         non_stp_search_words=[word for word in search_word_split if word not in highlight_words_stopword]
            #         stop_word_pos_list=[]
            #         if len(search_words.split())==1:
            #             phrase_re=re.compile(re.escape(' '+search_words),re.I)
            #             plain_text=phrase_re.sub('<em>'+search_words+'</em>',plain_text)
            #             # When the word comes inside double quotes
            #             plain_text=plain_text.replace("\""+search_words,"\""+'<em>'+search_words+'</em>')
            #         else:
            #             word_list=plain_text.split()
            #             pos_list=[]
            #             stop_word_pos_list=[]
            #             for highlight_word in non_stp_search_words:
            #                 if highlight_word.lower() in search_words.lower():
            #                     pos_list.extend([pos for pos, text in enumerate(word_list) if highlight_word.lower() in text.lower() and (len(text)-len(highlight_word)<=2)])
            #             pos_list=list(set(pos_list))
            #             pos_list.sort()
            #             for stpword in highlight_words_stopword:
            #                 if stpword.lower() in search_words.lower():

            #                     stop_word_pos_list.extend([pos for pos, text in enumerate(word_list) if text.lower() == stpword.lower()])
            #             # print(pos_list,'POSLIST')
            #             for index in range(len(pos_list)-1):
            #                 if len(non_stp_search_words)>1 and (pos_list[index+1]-pos_list[index]<=5):
            #                     if '<em>' not in word_list[pos_list[index]]  and ((word_list[pos_list[index]].lower() not in word_list[pos_list[index+1]].lower()) and (word_list[pos_list[index+1]].lower() not in word_list[pos_list[index]].lower())):
            #                         word_list[pos_list[index]]='<em>'+word_list[pos_list[index]]+'</em>'
            #                     if '<em>' not in word_list[pos_list[index+1]] and ((word_list[pos_list[index]].lower() not in word_list[pos_list[index+1]].lower()) and (word_list[pos_list[index+1]].lower() not in word_list[pos_list[index]].lower())):
            #                         word_list[pos_list[index+1]]='<em>'+word_list[pos_list[index+1]]+'</em>'
            #                 elif len(non_stp_search_words)==1:
            #                     for pos in pos_list:
            #                         for stp_pos in stop_word_pos_list:
            #                             if abs(pos-stp_pos)<=2 and  '<em>' not in word_list[pos]:
            #                                 word_list[pos]='<em>'+word_list[pos]+'</em>'

            #             for pos in pos_list:
            #                 for stp_pos in stop_word_pos_list:
            #                     if abs(pos-stp_pos)<=2 and word_list[pos].startswith('<em>') and  '<em>' not in word_list[stp_pos]:
            #                         word_list[stp_pos]='<em>'+word_list[stp_pos]+'</em>'
            #             plain_text=' '.join(word_list)


            if def_sub_search:
                for phrase in highlight_words_def:
                    phrase_re=re.compile(re.escape(phrase),re.I)
                    plain_text=phrase_re.sub('<ed>'+phrase+'</ed>',plain_text)

        #
        # for phrase in highlight_words:
        #      plain_text=plain_text.replace(phrase,'<em>'+phrase+'</em>')



        #From bold phrases

        key_phrases_bold=page['bold_phrases']
        key_phrases_bold=[i for i in key_phrases_bold if len(i)>3]
        key_phrases_bold=[i for i in key_phrases_bold if Ut.get_phrase_proximity(highlight_words,i,page['text'],super_list)<=word_proximity_limit]







        matches={}
        if is_clause:
            matches['text']=match_text
            matches['clause_score']=clause_score
        else:
            matches['text']=plain_text
        matches['azure_score']=page['@search.score']
        matches['language']=page['languageCode']
        matches['page']=int(page['page'])
        matches['doc_name']=page['doc_name']
        matches['country']=page['country']
        matches['lob']=lob
        matches["phrase_list"]= flat_super_list

        matches['is_clause']=is_clause
        if "folder" in page:
            matches['doc_collection']=page['folder']
        else:
            matches['doc_collection']="collection 00"
        matches['id']=page['id']
        def_search_list=[]
        if def_sub_search:
            for defs in page['definitions']:
                for word in highlight_words_user:
                    if word in defs['text']:
                        word_re=re.compile(re.escape(word),re.I)
                        defs['text']=word_re.sub('<em>'+word+'</em>',defs['text'])
                        if defs not in def_search_list:
                            def_search_list.append(defs)
            matches['highlight_words_def']=highlight_words_def
        else:
            matches['highlight_words_def']=[]


        matches['definitions']=def_search_list
        matches['bold_phrases']=key_phrases_bold
        matches['highlight_words']=highlight_words_user


        # return(json.dumps(page))
        matches['definitions_in_page']=page['definitions_in_page']

        matches['definition_text']=definition_text

        if not is_clause:
            proximity_dict={}
            for master_list in super_list:
                if len(master_list)>1:
                    proximity_in_word_count,cropped_text=Ut.proximity(proximity_lookup_text,master_list)
                    proximity_dict[cropped_text]=proximity_in_word_count
                elif len(master_list)==1:
                    proximity_in_word_count,cropped_text=Ut.single_level_proximity(proximity_lookup_text,master_list)
                    if cropped_text:
                        proximity_dict[cropped_text]=proximity_in_word_count


            if proximity_dict:
                cropped_text=min(proximity_dict,key=proximity_dict.get)
                proximity_in_words=proximity_dict[cropped_text]
            else:
                # print('A')
                cropped_text=''
                proximity_in_words=0

            matches['proximity']=proximity_in_words
            proximity_scores.append(proximity_in_words)
            matches['proximity_crop']=cropped_text

            if cropped_text=='Not applicable':
                matches['custom_score']=100

            elif cropped_text=='':
                matches['custom_score']=0
                continue
            elif  proximity_in_words >0:
                total_words=len(matches['text'].split())
                matches['custom_score']=(1-(proximity_in_words/total_words))*100

        fuzz_ratio=Ut.find_def_in_keys(highlight_words_user,page['definitions_in_page'])[1]
        if Ut.find_def_in_keys(highlight_words_user,page['definitions_in_page'])[0]:
            matches['definition_confidence']=round(80+(fuzz_ratio/5))

        else:
            try:
                matches['definition_confidence']=round(min(80,matches['custom_score']))
            except:
                matches['definition_confidence']=80

        if not content_exl_head:
            matches['exclusion_confidence']=Ut.confidence_bow(highlight_words_user,page['excl_pos'],plain_text)
        else:
            matches['exclusion_confidence']=100
        if not content_cond_head:
            matches['condition_confidence']=Ut.confidence_bow(highlight_words_user,page['cond_pos'],plain_text)
        else:
            matches['condition_confidence']=100
        if not content_ext_head:
            matches['extension_confidence']=Ut.confidence_bow(highlight_words_user,page['ext_pos'],plain_text)
        else:
            matches['extension_confidence']=100



        page['highlight_words']=highlight_words_user
        page['highlight_words_def']=highlight_words_def
        page['bold_phrases']=key_phrases_bold
        search_result[page['id']]=page
        matches_list.append(matches)


    if len(matches_list)==1 and  is_clause:
        matches_list[0]['score']=matches_list[0]['clause_score']

    elif len(matches_list)==1 and not is_definition:
        matches_list[0]['score']=matches_list[0]['custom_score']
    elif len(matches_list)==1 and is_definition:
        matches_list[0]['score']=matches_list[0]['definition_confidence']
    else:
        max_score=max(search_scores)
        min_score=min(search_scores)







        for match in matches_list:


            # bringing the azure score between 0 and 100

            # match['azure_score']=round(Ut.normalise(match['azure_score'],min_score,max_score))
            try:





                if match['is_clause'] and not is_definition :
                    match['score']=match['clause_score']

                elif is_definition and not and_operator_boolean:
                    match['score']=match['definition_confidence']

                elif is_extension and not and_operator_boolean:
                    match['score']=match['extension_confidence']
                elif is_exclusion and not and_operator_boolean:
                    match['score']=match['exclusion_confidence']
                elif is_condition and not and_operator_boolean:
                    match['score']=match['condition_confidence']

                elif search_string=='*':
                    match['score']=0

                elif 'custom_score' in match:
                    match['score']=match['custom_score']
                else:
                    match['score']=match['azure_score']



            except Exception as err:
                print('Exception while reassigning score:{}'.format(err))
                match['score']=0
    key_phrases_bold_aggregate=[]
    for match in matches_list:
        if match['score'] >=80:
            key_phrases_bold_aggregate.extend(match['bold_phrases'])





    # When clause and keyword search has reults from the same page we pick the one that has highes score so that there will be only one result from one pagenum
    pages_n_scores={}
    final_matches_list=[]
    if search_string=='*':
        final_matches_list=matches_list

    else:

        for match in matches_list:
            page=match['page']
            score=match['score']
            doc_name=match['doc_name']

            if (doc_name,page) not in pages_n_scores:
                if score!=0:
                    pages_n_scores[(doc_name,page)]=score
                    final_matches_list.append(match)
            else:
                if score!=0 and score>pages_n_scores[(doc_name,page)]:
                    pages_n_scores[(doc_name,page)]=score
                    final_matches_list.append(match)
                else:
                    pass



    response_dict={"results":final_matches_list}
    proximity_scores=[match['proximity'] for match in final_matches_list if 'proximity' in match]
    if proximity_scores:
        response_dict['min_proximity']=min(proximity_scores)
        response_dict['max_proximity']=max(proximity_scores)
        if list(set(proximity_scores))[0]!=0:
            response_dict['proximity_flag']=True
        else:
            response_dict['proximity_flag']=False

    else:
        response_dict['proximity_flag']=False




    response_dict['key_phrases_aggregate']=Ut.kephrase_process(key_phrases_bold_aggregate)


    return response_dict
