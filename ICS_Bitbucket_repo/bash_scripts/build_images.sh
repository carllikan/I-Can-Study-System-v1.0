#!/bin/bash
unset source_dir;
unset image_name;
unset image_path;
unset build_args;
unset special_modules;
unset final_build_args;

pushd () {
    command pushd "$@" > /dev/null
}

popd () {
    command popd "$@" > /dev/null
}

# generic function for building docker images

source_dir=$1
image_name=`echo ${source_dir} | tr '_' '-'`
build_args=${@: 2}
image_path="${REGION}-docker.pkg.dev/${PROJECT}/cloud-run-artifacts/${image_name}:latest"
# special_modules=("global_search_api" "mind_map_evaluation_api" "reflection_evaluation_api")
pushd $BITBUCKET_CLONE_DIR/cloudrun_source/${source_dir}
    echo "copy four files for the other modules";
    cp $BITBUCKET_CLONE_DIR/function_source/common_py_utils/{gcp,sql_orm,flask_utils,std_response}.py . ;
    # if [[ "${special_modules[*]}" == "${source_dir}" ]]; then
    #     echo "copy three files for the special modules";
    #     cp $BITBUCKET_CLONE_DIR/function_source/common_py_utils/{gcp,flask_utils,std_response}.py . ;
    # else
    #     echo "copy four files for the other modules";
    #     cp $BITBUCKET_CLONE_DIR/function_source/common_py_utils/{gcp,sql_orm,flask_utils,std_response}.py . ;
    # fi
    if (( ${#build_args[@]} )); then
        for arg in ${build_args[@]}; do
            final_build_args+="--build-arg ${arg} ";
        done
        docker build \
            ${final_build_args} \
            -t ${image_path} . ;
    else
        docker build \
            -t ${image_path} . ;
    fi
    docker push ${image_path}
    rm -rf {gcp,sql_orm,flask_utils,std_response}.py
    export image_path
popd

